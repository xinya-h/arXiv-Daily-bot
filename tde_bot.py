import arxiv
import requests
import json
import os

# ========== 从环境变量读取配置（云端GitHub Actions使用） ==========
DING_WEBHOOK = os.getenv("DING_WEBHOOK")
STATE_FILE = "seen_papers.json"
QUERY = '(("tidal disruption event" OR TDE OR "stellar disruption") AND (cat:astro-ph.HE OR cat:gr-qc))'

def load_seen():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_seen(seen_set):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen_set), f, ensure_ascii=False, indent=2)

def send_ding_markdown(title, md_text):
    msg = {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": md_text
        }
    }
    resp = requests.post(DING_WEBHOOK, json=msg, timeout=15)
    print("Dingtalk response:", resp.json())
    return resp.json()

def fetch_tde_papers():
    seen = load_seen()
    search = arxiv.Search(
        query=QUERY,
        max_results=20,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )
    client = arxiv.Client(
        page_size = 20,
        delay_seconds = 5, 
        num_retries = 5
    )
    new_papers = []
    for paper in client.results(search):
        arxiv_id = paper.entry_id.split("/")[-1]
        if arxiv_id not in seen:
            new_papers.append(paper)
            seen.add(arxiv_id)
    save_seen(seen)
    return new_papers

def main():
    print("==== 开始抓取TDE arXiv ====")
    papers = fetch_tde_papers()
    if not papers:
        send_ding_markdown("【TDE arXiv每日简报】", "✅ 今日暂无新TDE论文")
        print("无新论文")
        return

    md_content = "# 🌌 TDE arXiv 新论文\n\n"
    for p in papers:
        authors = ", ".join([a.name for a in p.authors[:3]])
        if len(p.authors)>3:
            authors += " et al."
        md_content += f"""
**{p.title}**
作者：{authors}
arXiv ID：{p.entry_id}
PDF：{p.pdf_url}
> {p.summary[:400]}...

"""
    send_ding_markdown("【TDE arXiv每日简报】", md_content)
    print(f"推送完成，共{len(papers)}篇新论文")

if __name__ == "__main__":
    main()
