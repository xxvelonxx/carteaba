"""
Scraper de posts de Threads para @simplifyinai
Estrategia principal: API interna de Threads con requests
Fallback: Playwright con headless shell
"""
import json
import time
import re
import requests

TARGET_PROFILE = "simplifyinai"
OUTPUT_FILE = "threads_posts.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}


def extract_posts_from_html(html: str) -> list:
    """Busca bloques JSON con posts dentro del HTML de Threads."""
    posts_found = []

    # Threads incrusta datos en script tags con __SSR_DATA__ o similar
    # Buscar arrays de posts en el HTML
    patterns = [
        r'"thread_items"\s*:\s*\[([^\]]+)\]',
        r'"edges"\s*:\s*\[([^\]]{20,})\]',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, html)
        for m in matches:
            try:
                data = json.loads(f"[{m}]")
                posts_found.extend(data)
            except Exception:
                pass

    # Buscar scripts con JSON completo
    script_blocks = re.findall(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>',
                               html, re.DOTALL)
    for block in script_blocks:
        try:
            data = json.loads(block)
            threads = find_threads_in_json(data)
            posts_found.extend(threads)
        except Exception:
            pass

    return posts_found


def find_threads_in_json(obj, depth=0):
    """Recorre recursivamente un objeto JSON buscando posts de Threads."""
    if depth > 10:
        return []
    results = []
    if isinstance(obj, dict):
        if "caption" in obj and "taken_at" in obj:
            # Formato Instagram-like
            results.append({
                "text": obj.get("caption", {}).get("text", "") if isinstance(obj.get("caption"), dict) else str(obj.get("caption", "")),
                "date": str(obj.get("taken_at", "")),
                "likes": obj.get("like_count", 0),
                "replies": obj.get("reply_count", 0),
                "reposts": obj.get("repost_count", 0) + obj.get("reshare_count", 0),
                "link": "",
            })
        else:
            for v in obj.values():
                results.extend(find_threads_in_json(v, depth + 1))
    elif isinstance(obj, list):
        for item in obj:
            results.extend(find_threads_in_json(item, depth + 1))
    return results


def scrape_via_requests() -> list:
    """Intenta obtener los posts usando la API pública de Instagram/Threads."""
    session = requests.Session()
    session.headers.update(HEADERS)
    posts = {}

    # ── Estrategia 1: API de Instagram con el username ───────────────────
    print("Intentando API de Instagram/Threads ...")
    try:
        # Primero obtener user_id del username
        lookup_url = f"https://www.threads.net/api/v1/users/usernameinfo/?username={TARGET_PROFILE}"
        r = session.get(lookup_url, timeout=15)
        print(f"  lookup status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            user_id = data.get("user", {}).get("pk") or data.get("user", {}).get("id")
            if user_id:
                print(f"  user_id encontrado: {user_id}")
                # Obtener threads del usuario
                threads_url = f"https://www.threads.net/api/v1/text_post_app/users/{user_id}/threads/?count=40"
                for cursor in [None] + [""] * 20:
                    params = {}
                    if cursor:
                        params["max_id"] = cursor
                    r2 = session.get(threads_url, params=params, timeout=15)
                    if r2.status_code != 200:
                        break
                    feed = r2.json()
                    items = feed.get("items", []) or feed.get("threads", [])
                    for item in items:
                        media = item.get("thread_items", [{}])[0].get("post", item) if item.get("thread_items") else item
                        text = media.get("caption", {}).get("text", "") if isinstance(media.get("caption"), dict) else str(media.get("caption", ""))
                        taken_at = media.get("taken_at", "")
                        key = text[:120]
                        if key and key not in posts:
                            posts[key] = {
                                "text": text,
                                "date": str(taken_at),
                                "date_label": "",
                                "likes": media.get("like_count", 0),
                                "replies": media.get("reply_count", 0) or media.get("text_post_app_info", {}).get("reply_count", 0),
                                "reposts": media.get("repost_count", 0),
                                "link": f"https://www.threads.net/@{TARGET_PROFILE}/post/{media.get('code','')}" if media.get("code") else "",
                            }
                    next_max_id = feed.get("next_max_id")
                    print(f"  Batch: +{len(items)} posts, total={len(posts)}, next={next_max_id}")
                    if not next_max_id or not items:
                        break
                    cursor = next_max_id
                    time.sleep(1.5)
    except Exception as e:
        print(f"  Error estrategia 1: {e}")

    if posts:
        return list(posts.values())

    # ── Estrategia 2: Scraping del HTML de la página de perfil ───────────
    print("Intentando scraping de página HTML ...")
    try:
        url = f"https://www.threads.net/@{TARGET_PROFILE}"
        r = session.get(url, timeout=20)
        print(f"  status: {r.status_code}, size: {len(r.text)}")
        if r.status_code == 200:
            extracted = extract_posts_from_html(r.text)
            for post in extracted:
                key = post.get("text", "")[:120]
                if key:
                    posts[key] = post
    except Exception as e:
        print(f"  Error estrategia 2: {e}")

    if posts:
        return list(posts.values())

    # ── Estrategia 3: Playwright headless shell ───────────────────────────
    print("Intentando Playwright headless shell ...")
    return scrape_via_playwright()


def scrape_via_playwright() -> list:
    """Fallback con Playwright usando el headless_shell instalado."""
    from playwright.sync_api import sync_playwright

    HEADLESS_SHELL = "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell"
    posts = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path=HEADLESS_SHELL,
            args=["--no-sandbox"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()

        url = f"https://www.threads.net/@{TARGET_PROFILE}"
        print(f"  Cargando {url} ...")
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(5000)

        no_new_count = 0
        scroll_round = 0

        while no_new_count < 10:
            scroll_round += 1
            articles = page.query_selector_all("article")
            for article in articles:
                spans = article.query_selector_all("span")
                text_parts = []
                for span in spans:
                    t = (span.inner_text() or "").strip()
                    if t and len(t) > 5 and t not in text_parts:
                        text_parts.append(t)
                raw_text = " ".join(text_parts[:10])
                if not raw_text or len(raw_text) < 10:
                    continue
                time_el = article.query_selector("time")
                date_str = time_el.get_attribute("datetime") if time_el else ""
                link_el = article.query_selector("a[href*='/post/']")
                link = link_el.get_attribute("href") if link_el else ""
                key = raw_text[:120]
                if key not in posts:
                    posts[key] = {"text": raw_text, "date": date_str,
                                  "likes": 0, "replies": 0, "reposts": 0,
                                  "link": f"https://www.threads.net{link}" if link.startswith("/") else link}

            count_before = len(posts)
            print(f"  Scroll #{scroll_round} — posts: {count_before}")
            page.evaluate("window.scrollBy(0, window.innerHeight * 3)")
            page.wait_for_timeout(2500)
            no_new_count = no_new_count + 1 if len(posts) == count_before else 0

        browser.close()

    return list(posts.values())


def main():
    result = scrape_via_requests()

    if not result:
        print("\n⚠️  No se pudieron extraer posts. Threads puede requerir login.")
        print("   Alternativa manual: https://apify.com/automation-lab/threads-scraper")
        return

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✅  {len(result)} posts guardados en '{OUTPUT_FILE}'")
    # Mostrar muestra
    print("\n--- Primeros 3 posts ---")
    for p in result[:3]:
        print(f"  [{p.get('date','')}] {p['text'][:100]}...")


if __name__ == "__main__":
    main()
