import requests
import json
import os
import time
from datetime import datetime

DING_WEBHOOK = os.getenv("DING_WEBHOOK")
STATE_FILE = "seen_papers.json"
BASE_URL = "https://export.arxiv.org/api/query"
QUERY = '(("tidal disruption event" OR TDE OR "stellar disruption") AND (cat:astro-ph.HE OR cat:gr-qc))'

def load_seen():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except json.JSONDecodeError:
            print("seen_papers.json parse error, reset")
    return set()

def save_seen(seen_set):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen_set), f, ensure_ascii=False, indent=2)

def send_ding_markdown(title, md_text):
    msg = {
        "msgtype": "markdown",
        "markdown": {"title": title, "text": md_text}
    }
    resp = requests.post(DING_WEBHOOK, json=msg, timeout=15)
    print("Ding response:", resp.status_code)
    return resp

def fetch_arxiv_with_retry(query, max_results=20, max_retry=5):
    params = {
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending"
    }
    for attempt in range(max_retry):
        try:
            resp = requests.get(BASE_URL, params=params, timeout=20)
            if resp.status_code == 429 or resp.status_code == 503:
                wait = 2 ** attempt
                print(f"429/503, retry after {wait}s")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            wait = 2 ** attempt
            print(f"Fetch error {e}, wait {wait}s")
            time.sleep(wait)
    raise Exception("Max retry reached, arXiv API unavailable")

def parse_atom(xml_str):
    # 简易解析atom feed，不依赖arxiv库
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml_str)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    papers = []
    for entry in root.findall("atom:entry", ns):
        entry_id = entry.find("atom:id", ns).text
        arxiv_id = entry_id.split("/")[-1]
        title = entry.find("atom:title", ns).text.strip()
        summary = entry.find("atom:summary", ns).text.strip()
        authors = [a.find("atom:name", ns).text for a in entry.findall("atom:author", ns)]
        pdf_url = None
        for link in entry.findall("atom:link", ns):
            if link.attrib.get("title") == "pdf":
                pdf_url = link.attrib["href"]
        papers.append({
            "id": arxiv_id,
            "title": title,
            "summary": summary,
            "authors": authors,
            "pdf": pdf_url
        })
    return papers

def main():
    try:
        print("==== Fetch TDE arXiv ====")
        xml = fetch_arxiv_with_retry(QUERY, max_results=20)
        papers = parse_atom(xml)
        seen = load_seen()
        new_papers = [p for p in papers if p["id"] not in seen]
        for p in new_papers:
            seen.add(p["id"])
        save_seen(seen)

        today = datetime.now().strftime("%Y-%m-%d")
        if not new_papers:
            send_ding_markdown("【TDE arXiv每日简报】", f"✅ {today} 暂无新TDE论文")
            print("No new papers")
            return

        md = f"# 🌌 TDE arXiv 新论文【{today}】\n\n"
        for p in new_papers:
            auth = ", ".join(p["authors"][:3])
            if len(p["authors"]) > 3:
                auth += " et al."
            md += f"""
**{p['title']}**
作者：{auth}
arXiv ID：{p['id']}
PDF：{p['pdf']}
> {p['summary'][:400]}...

"""
        send_ding_markdown("【TDE arXiv每日简报】", md)
        print(f"推送完成，新论文 {len(new_papers)}")
    except Exception as e:
        err_msg = f"TDE机器人异常\n{str(e)}"
        send_ding_markdown("【TDE arXiv机器人报错】", err_msg)
        print(err_msg)

if __name__ == "__main__":
    main()
