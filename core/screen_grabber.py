import logging
from PyQt6.QtGui import QGuiApplication, QImage, QPixmap, QRegion
from PyQt6.QtCore import QObject, QRect, QTimer, Qt
import numpy as np
import dxcam

# Disable dxcam log for deployment app.
# logging.getLogger("dxcam").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)


class DXScreenGrabber(QObject):
    def __init__(self, parent=None):
        # dxcam config.
        super().__init__(parent)
        self._cameras = []
        self._outputs = []
        self._targets = []

        # output pars
        self._virtual_rect = QRect()
        self._desktop_image = QImage()
        self._screens_dirty = True
        try:
            self._rebuild()
        except Exception:
            logger.exception("[Dxcam] rebuild cameras failed")

        # Debouncing timer
        self.debounce_timer = QTimer(self)
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.timeout.connect(self._rebuild)

    def invalidate(self) -> None:
        """
        Invalid grabber configuration and rebuild.
        """

        self._screens_dirty = True
        self.debounce_timer.start(5000)
        # try:
        #     self._rebuild()
        # except Exception:
        #     logger.exception("[Dxcam] rebuild cameras error")

    def _rebuild(self) -> None:
        """Call when the controller detects a display-layout change.
        virtual_rect (QRect):       covered (QRegion):

        +--------+--------+         +--------+
        | screen |  gap   |         | screen |
        +--------+--------+         +--------+--------+
        | screen | screen |         | screen | screen |
        +--------+--------+         +--------+--------+
        """
        if not self._screens_dirty:
            # skip if screen not dirty
            return
        # ---------------------------------------------
        # Create 1 big all screen virtual rect and empty image.
        # ---------------------------------------------

        logger.debug("[Dxcam] Re-building virtual screen & monintor cameras")
        screens = QGuiApplication.screens()
        if not screens:
            raise RuntimeError("No screens found")

        virtual_rect = QRect()
        covered = QRegion()

        for screen in screens:
            geometry = screen.geometry()
            virtual_rect = virtual_rect.united(geometry)
            covered = covered.united(QRegion(geometry))

        if virtual_rect.isEmpty():
            raise RuntimeError("Virtual desktop geometry is empty")

        desktop_image = QImage(virtual_rect.size(), QImage.Format.Format_RGB32)
        if desktop_image.isNull():
            raise RuntimeError("Could not allocate desktop image")

        has_gaps = covered != QRegion(virtual_rect)
        if has_gaps:
            desktop_image.fill(Qt.GlobalColor.black)

        targets = [
            screen.geometry().translated(-virtual_rect.left(), -virtual_rect.top())
            for screen in screens
        ]
        # ---------------------------------------------
        # Create cameras.
        # ---------------------------------------------
        self._create_cameras(screens)

        self._targets = targets
        self._virtual_rect = virtual_rect
        self._desktop_image = desktop_image
        self._screens_dirty = False

    def _create_cameras(self, screens) -> None:
        """
        This assumes Qt and DXcam report matching monitor origins;
        it deliberately fails rather than guessing if DPI scaling makes them differ.
        """
        self._release_cameras()
        self._cameras = []
        self._outputs = []

        if self._screens_dirty:
            self.refresh_factory_cache()

        try:
            # (left, top) -> (device_idx, output_idx)
            output_by_position = {}
            factory = getattr(dxcam, "__factory", None)
            if factory is None:
                raise RuntimeError("Cannot find DXcam Output Factory instance.")

            # factory.outputs ：[[device0_output0, device0_output1], [device1_output0, ...]]
            for device_idx, devices in enumerate(factory.outputs):
                for output_idx, output in enumerate(devices):
                    output.update_desc()
                    rect = output.desc.DesktopCoordinates
                    output_by_position[(rect.left, rect.top)] = (device_idx, output_idx)
            for screen in screens:
                geometry = screen.geometry()
                position = (geometry.x(), geometry.y())

                if position not in output_by_position:
                    raise RuntimeError(
                        f"No DXcam output at {position} "
                        f"for {screen.name()!r}; "
                        f"available={list(output_by_position.keys())}"
                    )
                device_idx, output_idx = output_by_position[position]
                camera = dxcam.create(
                    device_idx=device_idx,
                    output_idx=output_idx,
                    backend="dxgi",
                    processor_backend="numpy",
                    output_color="BGRA",
                )
                self._cameras.append(camera)
                self._outputs.append((device_idx, output_idx))

        except Exception:
            self._release_cameras()
            self._cameras = []
            self._outputs = []
            logger.exception("Creating camera failed")
            raise

    def refresh_factory_cache(self):
        """
        Private DXcam internals: version-dependent. Refresh the factory for device-loss recovery.

        DXcam’s factory caches Device objects, and dxcam.create() takes its device from that cache.
        Releasing cameras does not rebuild the factory’s device list.
        That why camera recreation can keep encountering the removed device.
        """
        factory = getattr(dxcam, "__factory", None)
        if factory is None:
            raise RuntimeError("Unsupported DXcam factory implementation")

        # Do not reset shared devices while other cameras are alive.
        active = [
            camera
            for camera in list(factory._camera_instances.values())
            if not camera.is_released
        ]
        if active:
            raise RuntimeError(
                "Cannot reset DXcam devices while other cameras are active"
            )
        factory._camera_instances.clear()
        # Re-enumerate adapters and create fresh Device/Output objects.
        # DXFactory() alone would return the existing singleton.
        factory.__init__()

    def _release_cameras(self) -> None:
        """
        Release camera before delete.
        """
        for camera in self._cameras:
            try:
                camera.release()
            except Exception:
                logger.warning("Releasing camera error, skipped releasing.")
                pass
        self._cameras.clear()

    def grab_all(self) -> tuple[QPixmap, QRect] | None:
        """Try once, then retry once if the result is None."""
        try:
            result = self._grab_all()
            if result is None:
                result = self._grab_all()
            return result
        except Exception:
            logger.exception("[Dxcam] grab_all failed")
            return None

    def _grab_all(self) -> tuple[QPixmap, QRect] | None:
        """
        Grab all the screens and return pixmap & virtual rect.
        """
        # logger.debug("[Dxcam] start grab all screens")
        # t0 = time.perf_counter_ns()
        if self._screens_dirty:
            self._rebuild()

        image = self._desktop_image
        bits = image.bits()
        bits.setsize(image.sizeInBytes())
        destination = np.frombuffer(bits, dtype=np.uint8)
        destination = destination.reshape(image.height(), image.bytesPerLine())

        for camera, target, output in zip(self._cameras, self._targets, self._outputs):
            frame = camera.grab(new_frame_only=False)
            if frame is None:
                self._screens_dirty = True
                return None
            height, width = frame.shape[:2]
            if frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 4:

                raise RuntimeError(
                    f"Expected BGRA uint8 frame, got "
                    f"shape={frame.shape}, dtype={frame.dtype}"
                )
            if (width, height) != (target.width(), target.height()):
                raise RuntimeError(
                    f"Size mismatch for output {output}: "
                    f"target={target.width()}x{target.height()}, "
                    f"frame={width}x{height}"
                )

            x = target.left()
            y = target.top()

            # A direct BGRA byte copy; no QPainter or color swap.
            destination[
                y : y + height,
                x * 4 : (x + width) * 4,
            ] = frame.reshape(height, width * 4)

        # Do not return or reuse a cached QPixmap: callers may still
        # display an earlier screenshot.
        pixmap = QPixmap.fromImage(image.copy())
        if pixmap.isNull():
            raise RuntimeError("Could not create desktop pixmap")

        # print(
        #     f"Prepare time: {(t_prepare - t0) / 1e6:.1f} ms"
        #     f" | grab raw: {(t_grab_end-t_grab_start) / 1_000_000:.1f} ms"
        #     f" | grab screens: {(t_copied - t_prepare) / 1e6:.1f} ms"
        #     f" | to pixmap: {(t_pixmap - t_copied) / 1e6:.1f} ms"
        #     f" | grab_all(): {(time.perf_counter_ns() - t0) / 1_000_000:.1f} ms"
        # )
        return pixmap, QRect(self._virtual_rect)

    def close(self) -> None:
        self._release_cameras()

    # def __create_cameras(self, screens) -> None:
    #     # Release existing cameras before recreating the same outputs.
    #     self._release_cameras()
    #     self._cameras = []
    #     self._outputs = []

    #     if self._screens_dirty:
    #         self.refresh_factory_cache()

    #     try:
    #         for i, _screen in enumerate(screens):
    #             camera = dxcam.create(
    #                 device_idx=0,  # GPU 0
    #                 output_idx=i,
    #                 backend="dxgi",
    #                 processor_backend="numpy",
    #                 output_color="BGRA",
    #             )
    #             self._cameras.append(camera)
    #             self._outputs.append((0, i))
    #     except Exception:
    #         self._release_cameras()
    #         self._cameras = []
    #         self._outputs = []
    #         logger.exception("Creating camera failed")
    #         raise

    # def __create_cameras(self, screens) -> None:
    #     """
    #     This assumes Qt and DXcam report matching monitor origins;
    #     it deliberately fails rather than guessing if DPI scaling makes them differ.
    #     """
    #     self._release_cameras()
    #     self._cameras = []
    #     self._outputs = []

    #     if self._screens_dirty:
    #         self.refresh_factory_cache()

    #     try:
    #         factory = getattr(dxcam, "__factory")
    #         outputs = factory.outputs[0]

    #         # Monitor position -> original DXcam output index.
    #         output_by_position = {}

    #         for output_idx, output in enumerate(outputs):
    #             output.update_desc()
    #             rect = output.desc.DesktopCoordinates
    #             output_by_position[(rect.left, rect.top)] = output_idx

    #         for screen in screens:
    #             geometry = screen.geometry()
    #             position = (geometry.x(), geometry.y())

    #             if position not in output_by_position:
    #                 raise RuntimeError(
    #                     f"No DXcam output at {position} "
    #                     f"for {screen.name()!r}; "
    #                     f"available={output_by_position}"
    #                 )

    #             output_idx = output_by_position[position]

    #             camera = dxcam.create(
    #                 device_idx=0,
    #                 output_idx=output_idx,
    #                 backend="dxgi",
    #                 processor_backend="numpy",
    #                 output_color="BGRA",
    #             )

    #             self._cameras.append(camera)
    #             self._outputs.append((0, output_idx))

    #     except Exception:
    #         self._release_cameras()
    #         self._cameras = []
    #         self._outputs = []
    #         logger.exception("Creating camera failed")
    #         raise


# if __name__ == "__main__":
#     import time
#     import sys

#     app = QApplication(sys.argv)

#     print(dxcam.output_info())
#     grabber = ScreenGrabber()
#     t0 = time.perf_counter_ns()
#     pixmaps = grabber.grab_all()
#     t1 = time.perf_counter_ns()

#     print(dxcam.output_info())
#     print([(s.name(), s.geometry()) for s in QApplication.screens()])

#     grabber = DXScreenGrabber()
#     # outputs=[
#     #     (0, 0),  # Qt screen 0: replace with its actual DXcam output
#     #     (0, 1),  # Qt screen 1: replace with its actual DXcam output
#     # ]
#     t2 = time.perf_counter_ns()
#     desktop_pixmap, virtual_rect = grabber.grab_all()
#     # On application shutdown:

#     print(f"mss capture time: {(t1-t0)// 1_000_000} ms")
#     print(f"dxcam capture time: {(time.perf_counter_ns()-t2)// 1_000_000} ms")
#     grabber.close()
