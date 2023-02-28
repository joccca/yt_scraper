"""
name:
  scrape_yt

description:
  Looks at YouTube search results – by netzpolitik.org, 2023

  The script uses a headless browser to collect YouTube search results
  for a set of search query and counts the results by its source (channel/creator).

usage:
  python3 ./scrape_yt.py  # set search queries and config in the script beforehand

author:
  jocca@netzpolitik.org

license:
    Copyright (c) 2023 jocca, netzpolitik.org

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation version 3 of the License.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program. If not, see https://www.gnu.org/licenses/gpl-3.0.en.html.
"""

import re
import time
import csv
import json
from typing import Iterator
from datetime import datetime
import asyncio
from urllib.parse import quote
from collections import OrderedDict
from pyppeteer import launch
import requests

# from termcolor import colored


def age_to_seconds(age_str: str) -> int:
    """
    converts age string to age in seconds for calculations
    """
    if "vor" in age_str:
        age_re = re.match(r"vor (\d+) (\w+)", age_str)
        if age_re[2] == "Sekunde" or age_re[2] == "Sekunden":
            age = int(age_re[1])
        elif age_re[2] == "Minute" or age_re[2] == "Minuten":
            age = 60 * int(age_re[1])
        elif age_re[2] == "Stunde" or age_re[2] == "Stunden":
            age = 60 * 60 * int(age_re[1])
        elif age_re[2] == "Tag" or age_re[2] == "Tagen":
            age = 24 * 60 * 60 * int(age_re[1])
        elif age_re[2] == "Woche" or age_re[2] == "Wochen":
            age = 7 * 24 * 60 * 60 * int(age_re[1])
        elif age_re[2] == "Monat" or age_re[2] == "Monaten":
            age = 30 * 24 * 60 * 60 * int(age_re[1])
        elif age_re[2] == "Jahr" or age_re[2] == "Jahren":
            age = 30 * 24 * 60 * 60 * 12 * int(age_re[1])
        else:
            raise ValueError(f'Age format not recognized: "{age_str}"')
    else:
        age = (
            24
            * 60
            * 60
            * (datetime.now() - datetime.strptime(age_str, "%d.%m.%Y")).days
        )

    return age


def get_writer(outfile) -> csv.writer:
    """
    creates csv wrtier
    """
    dialect = csv.excel()
    dialect.delimiter = ";"
    writer = csv.writer(
        outfile,
        dialect=dialect,
        quoting=csv.QUOTE_ALL,
    )
    return writer


def create_csv(name: str, header: list = None) -> object:
    """
    creates csv file and can write header
    """
    date = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    outfile = open(f"{date}-{name}.csv", "w", encoding="utf8")
    writer = get_writer(outfile)
    if header:
        writer.writerow(header)
    return writer


def write_results_to_csv(results: dict, name: str = "results") -> bool:
    """
    writes results to csv file
    """
    writer = create_csv(
        name,
        [
            "search term",
            "date scraped",
            "results page no",
            "age as displayed",
            "age in seconds",
            "source",
            "title",
            "url",
            "length",
        ],
    )

    for topic, pages in results.items():
        for page in pages:
            newrow = [topic] + list(page.values())
            writer.writerow(newrow)

    return True


def write_analysis_to_csv(results: dict, topics: list, name: str = "analysis") -> bool:
    """
    writes analysis to csv file
    """
    writer = create_csv(
        name,
        ["source"] + topics + ["total"],
    )

    for source, topics in results.items():
        writer.writerow([source] + list(topics.values()))

    return True


def analyze_sources(results: dict, topics: list) -> dict:
    """
    counts results by source
    """
    sources = {}

    for page_topic, pages in results.items():
        for page in pages:
            if page["source"] not in sources:
                sources[page["source"]] = {}
                for topic in topics:
                    sources[page["source"]][topic] = 0

            sources[page["source"]][page_topic] += 1

    for source, source_topics in sources.items():
        total = 0
        for topic_count in source_topics.values():
            total += topic_count
        sources[source]["total"] = total

    return OrderedDict(
        sorted(sources.items(), key=lambda i: i[1]["total"], reverse=True)
    )


def gen_dict_extract(key: str, var: dict) -> Iterator[str]:
    """
    creates generator to find values of `key` in a arbitrarily neasted dict/list-object
    source: https://stackoverflow.com/a/29652561
    """
    if hasattr(var, "items"):
        for k, v in var.items():
            if k == key:
                yield v
            if isinstance(v, dict):
                for result in gen_dict_extract(key, v):
                    yield result
            elif isinstance(v, list):
                for d in v:
                    for result in gen_dict_extract(key, d):
                        yield result


def trim_results(results: dict, max_length: int = 9999999) -> (dict, int):
    """
    trims dict of lists of results to same (shortest) length
    new_length = min(max_length, minimal_length_of_results)
    """
    count = 0

    for topic, res in results.items():
        new_length = len(res)
        count += new_length
        if new_length < max_length:
            max_length = new_length

    print(f"old result count: {count}")

    count = 0
    new_results = {}

    for topic, res in results.items():
        new_results[topic] = res[:max_length]
        count += max_length

    print(f"new result count: {count}, length per topic: {max_length}")

    return new_results, max_length


class YTScraper(object):
    """
    YouTube Scraper:handles browser session, cookies
    """

    def __init__(self):
        super().__init__()

        self.headers = {
            "user-agent": "Mozilla/5.0 (X11; Linux x86_64; rv:91.0) Gecko/20100101 Firefox/91.0"
        }

        self.yt_headers = {
            "host": "www.youtube.com",
            "referer": "https://www.youtube.com/",
        }

        self.cookie_defaults = {"PREF": "f6=40000000&tz=Europe.Berlin&hl=de&gl=DE"}
        self.cookies = []
        self.topics = []
        self.pages_total = 0
        self.results_total = 0
        self.browser = None
        self.page = None
        self.captchas = 0

    async def open_new_page_in_fg(self, url: str) -> None:
        """
        opens browser to solve captcha
        """
        if self.browser is None:
            self.browser = await launch(headless=False, autoClose=False)

        self.page = await self.browser.newPage()

        if self.cookies:
            for cookie in self.cookies:
                await self.page.setCookie(cookie)

        await self.page.goto(url, timeout=0)

    async def save_valid_cookie(self, overwrite: dict = None) -> None:
        """
        saves the cookie of the currently open browser and closes page
        """
        cookies_fresh = {c["name"]: c["value"] for c in await self.page.cookies()}
        print("Thank you! The fresh cookie was delicious!")

        if overwrite:
            for k, v in overwrite.items():
                cookies_fresh[k] = v
            print("Cookies overwritten with defaults.")

        self.cookies = cookies_fresh
        await self.page.close()

    def close_browser(self) -> None:
        """
        closes browser
        """
        asyncio.get_event_loop().run_until_complete(self.browser.disconnect())
        asyncio.get_event_loop().run_until_complete(self.browser.close())

    def set_topics(self, topics: list) -> list:
        """
        setter for topics, sorts list before setting
        """
        topics.sort()
        self.topics = topics
        return self.topics

    def search_topics(self, pages: int = 1) -> list:
        """
        performs search for each loaded topic in self.topics
        parameter pages is ignored so far, as yt loads result list dynamically, not paged
        """
        start = int(time.time())

        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.open_new_page_in_fg("https://youtube.com"))
        input(
            "Please resolve the captcha for me. I'm a bot. I cannot do that. (RETURN to continue)"
        )
        loop.run_until_complete(self.save_valid_cookie(self.cookie_defaults))

        results = {}
        for topic in self.topics:
            print(f"Scraping '{topic}'")
            results[topic] = self.search(topic)

        print(f"\ntotal results: {self.results_total}")

        print(f"scraped {len(results)} topics in {int(time.time()) - start} seconds")
        print(f"captchas resolved: {self.captchas}")

        return results

    def search(self, query: str) -> list:
        """
        main function, takes query, returns results of first num_pages as a list
        """
        page = 1
        self.pages_total += 1
        results = []

        url = f"https://www.youtube.com/results?search_query={quote(query)}"
        response = requests.get(
            url,
            headers=self.headers | self.yt_headers,
            cookies=self.cookies,
        )
        html = response.text

        initial_data_json = re.search(r"var ytInitialData = ([^<]*)", html)[1]
        initial_data_json = initial_data_json.replace(";", "")
        initial_data_json = initial_data_json.replace("\\u", "")

        # write json to file for debuging:
        # date = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        # open(f"{date}-{query}-page-{page}.json", "w", encoding="utf-8").write(
        #     initial_data_json
        # )

        initial_data = json.loads(initial_data_json)
        for video_renderer in gen_dict_extract("videoRenderer", initial_data):
            if "publishedTimeText" in video_renderer:
                # print results for debuging:
                # print(
                #     colored(video_renderer["videoId"], "blue"),
                #     colored(video_renderer["ownerText"]["runs"][0]["text"], "green"),
                #     video_renderer["title"]["runs"][0]["text"],
                # )

                length = "LIVE"  # if there is no length, it's a probably a live stream

                if (
                    "thumbnailOverlayTimeStatusRenderer"
                    in video_renderer["thumbnailOverlays"][0]
                ):
                    length = video_renderer["thumbnailOverlays"][0][
                        "thumbnailOverlayTimeStatusRenderer"
                    ]["text"]["simpleText"]

                age_str = video_renderer["publishedTimeText"]["simpleText"]
                results.append(
                    {
                        "date": datetime.now().strftime("%Y-%m-%d-%H-%M-%S"),
                        "page": page,
                        "age": age_str,
                        "age_sec": age_to_seconds(age_str),
                        "source": video_renderer["ownerText"]["runs"][0]["text"],
                        "title": video_renderer["title"]["runs"][0]["text"],
                        "url": video_renderer["videoId"],
                        "length": length,
                    }
                )
                self.results_total += 1
        return results


if __name__ == "__main__":
    topics1 = [
        "Olaf Scholz",
        "Robert Habeck",
        "Friedrich Merz",
        "Christian Lindner",
        "Karl Lauterbach",
        "Annalena Baerbock",
        "Markus Söder",
        "Alice Weidel",
        "Sarah Wagenknecht",
        "Klimakrise",
        "Feminismus",
        "Corona",
        "Impfung",
        "Rassismus",
        "Sexismus",
        "Ukraine",
        "Selensky",
        "Russland",
        "Putin",
        "Inflation",
        "LGBTQ",
        "Joe Biden",
        "Cannabis",
        "Gendern",
        "Energiekrise",
    ]

    topics2 = [
        "Klimalüge",
        "Plandemie",
        "Impfschäden",
        "Genderwahn",
        "Cancel Culture",
        "Schuldkult",
        "Überfremdung",
        "Asylanten",
        "Sozialtourismus",
        "George Soros",
        "SED-Nachfolgepartei",
        "GrünInnen",
        "Transaktivismus",
        "Systemmedien",
        "Mainstreammedien",
        "Zwangsgebühren",
        "Staatsfunk",
        "Politikdarsteller",
        "Volkszorn",
        "Corona-Diktatur",
        "Ausländerkriminalität",
        "Kulturbereicherer",
        "Polit-Kaste",
        "Bevölkerungsaustausch",
        "Meinungsdiktatur",
    ]

    scraper = YTScraper()
    scraper.set_topics(topics1)
    results1 = scraper.search_topics()
    scraper.close_browser()

    # write_results_to_csv(results1, "results-1-all")

    results1, l = trim_results(results1)

    scraper = YTScraper()
    scraper.set_topics(topics2)
    results2 = scraper.search_topics()
    scraper.close_browser()

    # write_results_to_csv(results2, "results-2-all")

    results2, l = trim_results(results2, l)
    # trim first result list again, in case minimal length of second result list is shorter
    results1, l = trim_results(results1, l)

    write_results_to_csv(results1, "results-1-trimmed")
    write_results_to_csv(results2, "results-2-trimmed")

    analysis1 = analyze_sources(results1, topics1)
    write_analysis_to_csv(analysis1, topics1, "analysis-1")

    analysis2 = analyze_sources(results2, topics2)
    write_analysis_to_csv(analysis2, topics2, "analysis-2")
