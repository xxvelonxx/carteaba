"""
INSTRUCCIONES:
1. Instala dependencias:
      pip install playwright
      playwright install chromium

2. Corre este script:
      python scrape_threads_LOCAL.py

3. Sube el archivo 'threads_posts.json' que genera a Claude para el análisis.

Requiere Python 3.8+ instalado localmente.
"""
import json
import time
from playwright.sync_api import sync_playwright

TARGET_PROFILE = "simplifyinai"
OUTPUT_FILE = "threads_posts.json"
SCROLL_PAUSE_SEC = 2.5
MAX_NO_NEW_SCROLLS = 15  # para si no cargan más posts


def parse_count(text: str) -> int:
    if not text:
        return 0
    text = text.strip().replace(",", "").replace(".", "")
    try:
        if text.upper().endswith("K"):
            return int(float(text[:-1]) * 1000)
        if text.upper().endswith("M"):
            return int(float(text[:-1]) * 1_000_000)
        return int(text)
    except ValueError:
        return 0


def scrape():
    posts = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,  # visible para evitar detección anti-bot
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
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
        print(f"Abriendo {url} ...")
        page.goto(url, wait_until="domcontentloaded", timeout=30000)

        # Esperar a que carguen posts iniciales
        page.wait_for_timeout(4000)

        # Cerrar posibles popups de login
        for selector in ["[aria-label='Close']", "button:has-text('No')", "[data-testid='modal-close']"]:
            try:
                btn = page.query_selector(selector)
                if btn and btn.is_visible():
                    btn.click()
                    page.wait_for_timeout(500)
            except Exception:
                pass

        no_new_count = 0
        scroll_num = 0

        while no_new_count < MAX_NO_NEW_SCROLLS:
            scroll_num += 1

            # Extraer posts de la página
            articles = page.query_selector_all("article")
            before = len(posts)

            for article in articles:
                # Texto principal
                raw_text = ""
                # Intentar varios selectores conocidos de Threads
                for sel in [
                    "[dir='auto'] span",
                    "span[style*='white-space']",
                    "div[data-pressable-container] span",
                ]:
                    el = article.query_selector(sel)
                    if el:
                        t = (el.inner_text() or "").strip()
                        if len(t) > 10:
                            raw_text = t
                            break

                # Fallback: concatenar todos los spans significativos
                if not raw_text:
                    spans = article.query_selector_all("span")
                    parts = []
                    for s in spans:
                        t = (s.inner_text() or "").strip()
                        if t and len(t) > 5 and t not in parts:
                            parts.append(t)
                    raw_text = " ".join(parts[:15])

                if not raw_text or len(raw_text) < 10:
                    continue

                # Fecha
                time_el = article.query_selector("time")
                date_iso = time_el.get_attribute("datetime") if time_el else ""
                date_label = (time_el.get_attribute("title") or
                              time_el.inner_text() or "") if time_el else ""

                # Métricas
                likes = replies = reposts = 0
                for el in article.query_selector_all("[aria-label]"):
                    label = (el.get_attribute("aria-label") or "").lower()
                    val = parse_count(el.inner_text())
                    if "like" in label or "me gusta" in label:
                        likes = max(likes, val)
                    elif "repl" in label or "respue" in label or "comment" in label:
                        replies = max(replies, val)
                    elif "repost" in label or "rethread" in label or "compart" in label:
                        reposts = max(reposts, val)

                # Link
                link_el = article.query_selector("a[href*='/post/']")
                href = link_el.get_attribute("href") if link_el else ""
                full_link = f"https://www.threads.net{href}" if href.startswith("/") else href

                key = raw_text[:120]
                if key not in posts:
                    posts[key] = {
                        "text": raw_text,
                        "date": date_iso,
                        "date_label": date_label,
                        "likes": likes,
                        "replies": replies,
                        "reposts": reposts,
                        "link": full_link,
                    }

            new_count = len(posts)
            print(f"  Scroll #{scroll_num} → {new_count} posts únicos acumulados")

            # Scroll hacia abajo
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(SCROLL_PAUSE_SEC)

            if new_count == before:
                no_new_count += 1
            else:
                no_new_count = 0

        browser.close()

    result = list(posts.values())
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✅  Extracción completa: {len(result)} posts guardados en '{OUTPUT_FILE}'")
    print(f"   → Ahora sube '{OUTPUT_FILE}' a Claude para el análisis.")
    return result


if __name__ == "__main__":
    scrape()
