#!/usr/bin/env python3
"""
评论自动互动模块
通过 Playwright 抓取小红书评论，用 AI 生成个性化回复
"""

import json
import time
import logging
import sys
from pathlib import Path

log = logging.getLogger(__name__)

SKILL_DIR = Path(__file__).parent.parent
DATA_DIR = SKILL_DIR / 'data'
DATA_DIR.mkdir(exist_ok=True)

COMMENTS_DB = DATA_DIR / 'comments.json'
XHS_COMMENTS = 'https://creator.xiaohongshu.com/comment'


# ============ 数据库操作 ============

def _load_db():
    """加载评论数据库"""
    if COMMENTS_DB.exists():
        try:
            with open(COMMENTS_DB, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"replied": [], "stats": {"total_fetched": 0, "total_replied": 0}}


def _save_db(db):
    """保存评论数据库"""
    with open(COMMENTS_DB, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def _is_replied(db, comment_id):
    """检查是否已回复"""
    return comment_id in db.get('replied', [])


def _mark_replied(db, comment_id):
    """标记为已回复"""
    if comment_id not in db['replied']:
        db['replied'].append(comment_id)
        # 保留最近 2000 条
        if len(db['replied']) > 2000:
            db['replied'] = db['replied'][-2000:]
    db['stats']['total_replied'] = db['stats'].get('total_replied', 0) + 1
    _save_db(db)


# ============ 核心功能 ============

def fetch_comments(page, limit=20):
    """
    从创作者中心抓取评论
    返回: [{"id", "author", "content", "note_title", "time", "item"}]
    """
    log.info(f'抓取评论（最多 {limit} 条）...')
    page.goto(XHS_COMMENTS, wait_until='domcontentloaded', timeout=15000)
    time.sleep(3)

    # 尝试点击"未回复"筛选
    try:
        unreplied_tab = page.locator('text=未回复').first
        if unreplied_tab.is_visible(timeout=3000):
            unreplied_tab.click()
            time.sleep(2)
            log.info('已切换到未回复评论')
    except Exception:
        pass

    comments = []
    seen = set()

    # 滚动加载
    for _ in range(min(limit // 5 + 1, 10)):
        items = page.locator('.comment-item, [class*="comment-item"]').all()
        if not items:
            items = page.locator('.comment-container > div').all()

        for item in items:
            try:
                # 提取评论内容
                content_el = item.locator('[class*="content"], .comment-content').first
                content = content_el.inner_text(timeout=2000).strip() if content_el.is_visible(timeout=1000) else ''
                if not content:
                    continue

                # 生成唯一ID
                comment_id = str(hash(content))[:12]
                if comment_id in seen:
                    continue
                seen.add(comment_id)

                # 提取作者
                author = ''
                try:
                    author_el = item.locator('[class*="author"], [class*="nickname"]').first
                    author = author_el.inner_text(timeout=1000).strip()
                except Exception:
                    pass

                # 提取笔记标题
                note_title = ''
                try:
                    title_el = item.locator('[class*="note-title"], [class*="title"]').first
                    note_title = title_el.inner_text(timeout=1000).strip()
                except Exception:
                    pass

                # 提取时间
                comment_time = ''
                try:
                    time_el = item.locator('[class*="time"]').first
                    comment_time = time_el.inner_text(timeout=1000).strip()
                except Exception:
                    pass

                comments.append({
                    "id": comment_id,
                    "author": author,
                    "content": content,
                    "note_title": note_title,
                    "time": comment_time,
                    "item": item,
                })

                if len(comments) >= limit:
                    break
            except Exception:
                continue

        if len(comments) >= limit:
            break

        page.evaluate('window.scrollBy(0, 800)')
        time.sleep(1.5)

    log.info(f'共抓取 {len(comments)} 条评论')
    return comments[:limit]


def generate_reply(comment_content, note_title='', author='', style='friendly'):
    """
    用 AI 生成评论回复
    style: friendly(友好), humorous(幽默), brief(简短)
    """
    sys.path.insert(0, str(Path(__file__).parent))
    from content_gen import _call_llm

    style_map = {
        'friendly': '友好亲切、有温度，像朋友聊天',
        'humorous': '幽默风趣，适当用emoji',
        'brief': '简短精炼，一两句话',
    }
    style_desc = style_map.get(style, style_map['friendly'])

    prompt = f"""你是小红书博主，回复粉丝评论。

笔记: {note_title or '(未知)'}
粉丝: {author or '匿名'}
评论: {comment_content}

要求：{style_desc}，10-50字，真诚自然，有emoji但不超过2个。
直接输出回复内容："""

    try:
        reply = _call_llm(prompt, max_tokens=150).strip().strip('"').strip("'")
        return reply[:80] if len(reply) > 80 else reply
    except Exception as e:
        log.error(f'AI生成回复失败: {e}')
        return None


def reply_to_comment(page, item, reply_text):
    """
    回复单条评论
    """
    try:
        # 点击回复按钮
        reply_btn = item.locator('text=回复').first
        if not reply_btn.is_visible(timeout=3000):
            item.hover()
            time.sleep(0.5)
            reply_btn = item.locator('text=回复').first
        reply_btn.click(timeout=3000)
        time.sleep(0.5)

        # 输入回复
        input_box = page.locator('[contenteditable="true"]').last
        input_box.click()
        for char in reply_text:
            input_box.type(char, delay=30)
        time.sleep(0.3)

        # 发送
        send_btn = page.locator('text=发送').last
        if send_btn.is_visible(timeout=2000):
            send_btn.click()
        else:
            input_box.press('Enter')

        time.sleep(1)
        return True
    except Exception as e:
        log.error(f'回复失败: {e}')
        return False


def auto_reply(page, limit=10, style='friendly', dry_run=False):
    """
    自动回复评论
    返回: {"total", "replied", "skipped", "failed", "details"}
    """
    db = _load_db()
    comments = fetch_comments(page, limit=limit)
    db['stats']['total_fetched'] = db['stats'].get('total_fetched', 0) + len(comments)

    results = {"total": len(comments), "replied": 0, "skipped": 0, "failed": 0, "details": []}

    for comment in comments:
        cid = comment['id']

        # 跳过已回复
        if _is_replied(db, cid):
            results['skipped'] += 1
            continue

        # 生成回复
        reply = generate_reply(
            comment_content=comment['content'],
            note_title=comment.get('note_title', ''),
            author=comment.get('author', ''),
            style=style,
        )

        if not reply:
            results['failed'] += 1
            results['details'].append({"comment": comment['content'][:50], "status": "ai_failed"})
            continue

        detail = {"author": comment.get('author', ''), "comment": comment['content'][:80], "reply": reply}

        if dry_run:
            results['replied'] += 1
            detail['status'] = 'dry_run'
        else:
            success = reply_to_comment(page, comment['item'], reply)
            if success:
                _mark_replied(db, cid)
                results['replied'] += 1
                detail['status'] = 'sent'
                time.sleep(3)  # 避免频繁
            else:
                results['failed'] += 1
                detail['status'] = 'send_failed'

        results['details'].append(detail)

    _save_db(db)
    return results


def get_stats():
    """获取统计"""
    db = _load_db()
    return {
        "total_replied": db['stats'].get('total_replied', 0),
        "total_fetched": db['stats'].get('total_fetched', 0),
    }


def format_results(results):
    """格式化结果"""
    lines = [f"💬 评论互动", f"总计: {results['total']} | 已回复: {results['replied']} | 跳过: {results['skipped']} | 失败: {results['failed']}", ""]
    for d in results.get('details', []):
        icon = {"sent": "✅", "dry_run": "👀", "ai_failed": "⚠️", "send_failed": "❌"}.get(d['status'], "?")
        lines.append(f"{icon} [{d.get('author', '匿名')}] {d['comment'][:30]}")
        if d.get('reply'):
            lines.append(f"   → {d['reply']}")
    return "\n".join(lines)


# ============ CLI ============

def main():
    import argparse
    parser = argparse.ArgumentParser(description='小红书评论互动')
    sub = parser.add_subparsers(dest='action')

    sub.add_parser('fetch', help='抓取评论').add_argument('--limit', type=int, default=10)

    p = sub.add_parser('reply', help='自动回复')
    p.add_argument('--limit', type=int, default=10)
    p.add_argument('--style', choices=['friendly', 'humorous', 'brief'], default='friendly')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--headless', action='store_true')

    sub.add_parser('stats', help='查看统计')

    args = parser.parse_args()

    if args.action == 'stats':
        print(json.dumps(get_stats(), ensure_ascii=False, indent=2))
        return

    if args.action in ('fetch', 'reply'):
        from playwright.sync_api import sync_playwright
        sys.path.insert(0, str(Path(__file__).parent))
        from xhs_auto import create_browser_context, check_login

        with sync_playwright() as pw:
            ctx = create_browser_context(pw, headless=getattr(args, 'headless', False))
            page = ctx.pages[0] if ctx.pages else ctx.new_page()

            if not check_login(page):
                print(json.dumps({"success": False, "error": "未登录"}))
                ctx.close()
                return

            if args.action == 'fetch':
                comments = fetch_comments(page, limit=args.limit)
                print(json.dumps(comments, ensure_ascii=False, indent=2))
            elif args.action == 'reply':
                results = auto_reply(page, limit=args.limit, style=args.style, dry_run=args.dry_run)
                print(format_results(results))

            ctx.close()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
