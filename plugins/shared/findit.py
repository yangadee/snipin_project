"""
version 1.1
support air id

"""

from dataclasses import dataclass
import logging

import requests
from PyQt6.QtCore import QThread, pyqtSignal
from bs4 import BeautifulSoup
from requests.packages import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


@dataclass(frozen=True)
class FindItResult:
    kind: str  # e.g. "coach", "sap", "air", "procedure"
    title: str
    subtitle: str = ""
    link: str = ""


class Findit(QThread):
    """
    Asynchronous Background Worker Thread handling the web search pipeline.
    Prevents the PyQt6 GUI from freezing during slow network latency timeouts.
    """

    # --- Thread Safe Communication Signals ---
    result_readay = pyqtSignal(list)

    def __init__(self, search_targets, parent=None):
        super().__init__(parent)
        if isinstance(search_targets, str):
            self.search_targets = [search_targets]  # prevent only 1 str.
        else:
            self.search_targets = search_targets

    def run(self):
        """
        Core isolated workflow execution loop running completely on the background thread.
        This overrides the standard QThread.run() entry protocol method.
        """
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        session = requests.Session()
        session.verify = False
        result_data = []
        # print(f"search target:{self.search_targets}")
        for search_target in self.search_targets:
            # print("current search", search_target)
            url = f"https://findit.asml.com/search?q={search_target}"
            try:
                # 2. Perform HTTP GET request safely bypassing SSL checks
                response = session.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                result_html = response.text

                soup = BeautifulSoup(result_html, "html.parser")

                # Emulates: Containers := html.querySelectorAll('[class="card-body"]')
                # In CSS standard format, class selections are queried using a leading dot ('.')
                containers = soup.select(".card-body")

                if len(containers) < 1:
                    # print("[Status] Nothing found!!!")
                    continue

                # ============================================================
                # Pass 1: Search ALL containers for Coach
                # ============================================================
                coach_found = False
                for container in containers:
                    # print(container)
                    matches = container.select(
                        "a[href*='https://coach.asml.com/Coach/']"
                    )
                    target_url = ""
                    if len(matches) >= 1:
                        target_anchor = matches[0]
                        target_url = target_anchor.get("href")
                        # Try looking for coach title
                        term_span = target_anchor.find("span", class_="glossary-term")
                        coach_title = ""
                        if term_span:
                            coach_title = term_span.text.strip()
                            # print(f"Coach title: {coach_title}")

                        # result_data.append(
                        #     {
                        #         "text": f"{search_target}",
                        #         "url": f"{target_url}",
                        #         "tooltip": f"{coach_title}",
                        #         "subtitle": f"{coach_title}",
                        #         "type": "ℂ",
                        #     },
                        # )
                        result_data.append(
                            FindItResult(
                                kind="procedure",
                                title=search_target,
                                subtitle=coach_title,
                                link=target_url,
                            )
                        )
                        coach_found = True
                        break

                if coach_found:
                    continue
                # ============================================================
                # Pass 2: No Coach anywhere, look for other types
                # ============================================================
                for container in containers:
                    # ------------------------------------------------
                    # Cerberus
                    # ------------------------------------------------
                    cerberus_matches = container.select(
                        'a[href*="https://part-info.ais.asml.com/12nc"]'
                    ) or container.select('a[href*="https://cerberus.asml.com/"]')
                    cerberus_url = ""
                    if len(cerberus_matches) >= 1:
                        cerberus_anchor = cerberus_matches[0]
                        cerberus_url = cerberus_anchor.get("href")
                        # result_data.append(
                        #     {
                        #         "text": f"{search_target}",
                        #         "url": f"{cerberus_url}",
                        #         "type": "♺",
                        #     },
                        # )
                        result_data.append(
                            FindItResult(
                                kind="cerberus",
                                title=search_target,
                                subtitle="cerberus",
                                link=cerberus_url,
                            )
                        )
                        break
                    # ------------------------------------------------
                    # Service Order
                    # ------------------------------------------------
                    SO_matches = container.select(
                        "a[href*='https://net.asml.com/sap/']"
                    )
                    SO_url = ""
                    if len(SO_matches) >= 1:
                        SO_anchor = SO_matches[0]
                        SO_url = SO_anchor.get("href")
                        # result_data.append(
                        #     {
                        #         "text": f"{search_target}",
                        #         "url": f"{SO_url}",
                        #         "type": "S",
                        #     },
                        # )
                        result_data.append(
                            FindItResult(
                                kind="service_order",
                                title=search_target,
                                subtitle="service order",
                                link=SO_url,
                            )
                        )
                        break
                    # ------------------------------------------------
                    # AIR
                    # ------------------------------------------------
                    air_id_matches = container.select(
                        "a[href*='https://air.asml.com/']"
                    )
                    air_url = ""
                    if len(air_id_matches) >= 1:
                        air_anchor = air_id_matches[0]
                        air_url = air_anchor.get("href")
                        # result_data.append(
                        #     {
                        #         "text": f"{search_target}",
                        #         "url": f"{air_url}",
                        #         "type": "A",
                        #     },
                        # )
                        result_data.append(
                            FindItResult(
                                kind="air",
                                title=search_target,
                                subtitle="AIR",
                                link=air_url,
                            )
                        )
                        break

            except requests.exceptions.RequestException as e:
                # print(f"[Network Error] Execution workflow interrupted: {e}")
                logging.debug("[Network Error] Execution workflow interrupted: %s", e)
        self.result_readay.emit(result_data)
