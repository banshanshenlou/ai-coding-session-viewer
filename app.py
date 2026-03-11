"""
OpenCode Session Viewer - Backend API
轻量级 AI 会话历史查看器 (支持 OpenCode / Codex / Claude Code)
"""

import os
import json
import sqlite3
import glob as glob_module
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Literal, Tuple, Any
from contextlib import contextmanager
from enum import Enum
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen

from fastapi import FastAPI, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel

# 数据源枚举
class DataSource(str, Enum):
    OPENCODE = "opencode"
    CODEX = "codex"
    CLAUDE_CODE = "claude_code"

def expand_config_path(raw_path: str) -> Path:
    """展开环境变量和用户目录，避免跨机器时依赖固定绝对路径。"""
    return Path(os.path.expandvars(raw_path)).expanduser()


def get_local_appdata_dir() -> Path:
    """返回当前用户的 LocalAppData 目录，用于兼容 Windows 默认数据目录。"""
    local_appdata = os.getenv("LOCALAPPDATA")
    if local_appdata:
        return expand_config_path(local_appdata)
    return Path.home() / "AppData" / "Local"


def resolve_config_path(
    path_env_names: List[str],
    home_env_names: List[str],
    suffix: Optional[str],
    default_paths: List[Path],
) -> Path:
    """优先读取显式路径环境变量，其次读取 home 目录变量，最后回退到常见默认目录。"""
    for env_name in path_env_names:
        raw_value = os.getenv(env_name)
        if raw_value:
            return expand_config_path(raw_value)

    for env_name in home_env_names:
        raw_value = os.getenv(env_name)
        if raw_value:
            base_path = expand_config_path(raw_value)
            return base_path / suffix if suffix else base_path

    for candidate in default_paths:
        if candidate.exists():
            return candidate

    return default_paths[0]


LOCAL_APPDATA = get_local_appdata_dir()

# 数据源路径配置
CONFIG = {
    DataSource.OPENCODE: {
        "db_path": resolve_config_path(
            path_env_names=["OPENCODE_DB_PATH"],
            home_env_names=["OPENCODE_HOME"],
            suffix="opencode.db",
            default_paths=[
                Path.home() / ".local" / "share" / "opencode" / "opencode.db",
                LOCAL_APPDATA / "OpenCode" / "opencode.db",
                LOCAL_APPDATA / "opencode" / "opencode.db",
            ],
        ),
    },
    DataSource.CODEX: {
        "sessions_path": resolve_config_path(
            path_env_names=["CODEX_SESSIONS_PATH"],
            home_env_names=["CODEX_HOME"],
            suffix="sessions",
            default_paths=[
                Path.home() / ".codex" / "sessions",
            ],
        ),
    },
    DataSource.CLAUDE_CODE: {
        "projects_path": resolve_config_path(
            path_env_names=["CLAUDE_PROJECTS_PATH"],
            home_env_names=["CLAUDE_HOME"],
            suffix="projects",
            default_paths=[
                Path.home() / ".claude" / "projects",
            ],
        ),
    },
}

app = FastAPI(title="OpenCode Session Viewer", version="2.0.0")


# ==================== 数据模型 ====================

class Project(BaseModel):
    id: str
    name: Optional[str]
    worktree: str
    session_count: int


class SessionSummary(BaseModel):
    id: str
    title: str
    directory: str
    time_created: str
    time_updated: str
    message_count: int
    summary_additions: Optional[int]
    summary_deletions: Optional[int]


class Message(BaseModel):
    id: str
    role: str
    time_created: str
    content: Optional[str]
    tokens_input: Optional[int]
    tokens_output: Optional[int]
    parts: List[dict]


class SearchResult(BaseModel):
    session_id: str
    session_title: str
    message_id: str
    role: str
    snippet: str
    time_created: str


# ==================== 数据库连接 ====================

@contextmanager
def get_opencode_db():
    """只读模式连接 OpenCode 数据库"""
    db_path = CONFIG[DataSource.OPENCODE]["db_path"]
    if not db_path.exists():
        raise FileNotFoundError(f"OpenCode DB not found: {db_path}")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def is_opencode_available() -> bool:
    """判断 OpenCode 数据库是否可用，避免其他数据源被无关依赖拖垮。"""
    return CONFIG[DataSource.OPENCODE]["db_path"].exists()


def build_search_snippet(text: str, query: str) -> str:
    """为搜索结果生成上下文片段，便于不同数据源保持一致展示。"""
    lowered_text = text.lower()
    lowered_query = query.lower()
    idx = lowered_text.find(lowered_query)
    if idx >= 0:
        start = max(0, idx - 50)
        end = min(len(text), idx + len(query) + 50)
        return "..." + text[start:end] + "..."
    return (text[:100] + "...") if len(text) > 100 else text


def get_file_session_summary(source: DataSource, session_id: str) -> Optional[dict]:
    """按数据源获取文件型会话摘要，用于导出和其他只读操作。"""
    if source == DataSource.CODEX:
        sessions = get_codex_sessions()
    elif source == DataSource.CLAUDE_CODE:
        sessions = get_claude_code_sessions()
    else:
        return None

    session = next((item for item in sessions if item["id"] == session_id), None)
    return normalize_session_summary(session) if session else None


def search_file_sessions(source: DataSource, query: str, limit: int) -> List[SearchResult]:
    """为 Codex / Claude Code 提供文件型会话搜索，避免搜索功能强依赖 OpenCode。"""
    results: List[SearchResult] = []

    if source == DataSource.CODEX:
        sessions = get_codex_sessions()
    elif source == DataSource.CLAUDE_CODE:
        sessions = get_claude_code_sessions()
    else:
        return results

    for session in sessions:
        messages = get_session_messages(session["id"], source)
        for message in messages:
            content = message.content or ""
            if not content or query.lower() not in content.lower():
                continue

            results.append(SearchResult(
                session_id=session["id"],
                session_title=session["title"],
                message_id=message.id,
                role=message.role,
                snippet=build_search_snippet(content, query),
                time_created=message.time_created,
            ))
            if len(results) >= limit:
                return results

    return results


def search_opencode_sessions(query: str, limit: int) -> List[SearchResult]:
    """搜索 OpenCode 消息内容，供 OpenCode 模式或聚合搜索复用。"""
    if not is_opencode_available():
        return []

    with get_opencode_db() as conn:
        cur = conn.execute("""
            SELECT 
                p.id as part_id,
                p.message_id,
                p.session_id,
                p.time_created,
                p.data as part_data,
                m.data as message_data,
                s.title as session_title
            FROM part p
            JOIN message m ON p.message_id = m.id
            JOIN session s ON m.session_id = s.id
            WHERE s.parent_id IS NULL 
              AND s.title NOT LIKE '%subagent%'
              AND p.data LIKE ?
            ORDER BY p.time_created DESC
            LIMIT ?
        """, (f"%{query}%", limit))

        results = []
        for row in cur.fetchall():
            message_data = json.loads(row["message_data"])
            part_data = row["part_data"]
            results.append(SearchResult(
                session_id=row["session_id"],
                session_title=row["session_title"],
                message_id=row["message_id"],
                role=message_data.get("role", "unknown"),
                snippet=build_search_snippet(part_data, query),
                time_created=format_timestamp(row["time_created"])
            ))

        return results


def print_source_path_status(source: DataSource, label: str, env_hints: List[str], path_key: str):
    """打印解析后的数据路径与缺失提示，方便跨机器排查环境问题。"""
    path = CONFIG[source][path_key]
    print(f"{label}: {path}")
    if not path.exists():
        print(f"  -> 未找到，若目录不在默认位置，请设置环境变量: {', '.join(env_hints)}")


def should_open_browser() -> bool:
    """允许通过环境变量关闭自动开页，避免无桌面环境下误报。"""
    return os.getenv("OPENCODE_VIEWER_OPEN_BROWSER", "1") not in {"0", "false", "False"}


def schedule_browser_open(url: str):
    """等待本地服务可访问后再打开浏览器，减少启动瞬间空白页概率。"""
    delay_seconds = float(os.getenv("OPENCODE_VIEWER_OPEN_BROWSER_DELAY", "0.6"))
    timeout_seconds = float(os.getenv("OPENCODE_VIEWER_OPEN_BROWSER_TIMEOUT", "15"))

    def _open_browser():
        time.sleep(delay_seconds)
        deadline = time.time() + timeout_seconds

        while time.time() < deadline:
            try:
                with urlopen(url, timeout=1):
                    break
            except URLError:
                time.sleep(0.5)
            except OSError:
                time.sleep(0.5)

        try:
            opened = webbrowser.open(url)
            if not opened:
                print(f"浏览器未自动打开，请手动访问: {url}")
        except Exception as exc:
            print(f"自动打开浏览器失败，请手动访问: {url} ({exc})")

    threading.Thread(target=_open_browser, daemon=True).start()


def resolve_server_config() -> Tuple[str, int, str]:
    """从环境变量解析监听地址与浏览器地址，避免提示地址和实际监听端口不一致。"""
    raw_url = os.getenv("OPENCODE_VIEWER_URL", "http://localhost:8765").strip()
    normalized_url = raw_url if "://" in raw_url else f"http://{raw_url}"
    parsed = urlparse(normalized_url)

    host = parsed.hostname or "127.0.0.1"
    if parsed.port is not None:
        port = parsed.port
    elif parsed.scheme == "https":
        port = 443
    else:
        port = 80

    return host, port, normalized_url


# ==================== 数据源适配器 ====================

def get_codex_sessions() -> List[dict]:
    """获取 Codex 会话列表"""
    sessions_path = CONFIG[DataSource.CODEX]["sessions_path"]
    sessions = []
    
    if not sessions_path.exists():
        return sessions
    
    # 查找所有 JSONL 文件
    for year_dir in sorted(sessions_path.iterdir(), reverse=True):
        if not year_dir.is_dir():
            continue
        for month_dir in sorted(year_dir.iterdir(), reverse=True):
            if not month_dir.is_dir():
                continue
            for day_dir in sorted(month_dir.iterdir(), reverse=True):
                if not day_dir.is_dir():
                    continue
                for jsonl_file in day_dir.glob("rollout-*.jsonl"):
                    # 读取第一条获取 session 元数据
                    try:
                        with open(jsonl_file, 'r', encoding='utf-8') as f:
                            first_line = f.readline()
                            if first_line:
                                data = json.loads(first_line)
                                if data.get("type") == "session_meta":
                                    payload = data.get("payload", {})
                                    sessions.append({
                                        "id": payload.get("id"),
                                        "title": payload.get("cwd", jsonl_file.stem),
                                        "directory": payload.get("cwd", ""),
                                        "time_created": payload.get("timestamp", ""),
                                        "time_updated": str(jsonl_file.stat().st_mtime),
                                        "message_count": sum(1 for _ in open(jsonl_file, encoding='utf-8', errors='ignore')),
                                        "source": "codex"
                                    })
                    except (json.JSONDecodeError, OSError):
                        continue
    
    return sessions


def get_claude_code_sessions() -> List[dict]:
    """获取 Claude Code 会话列表"""
    projects_path = CONFIG[DataSource.CLAUDE_CODE]["projects_path"]
    sessions = []
    
    if not projects_path.exists():
        return sessions
    
    # 查找所有 JSONL 文件
    for project_dir in projects_path.iterdir():
        if not project_dir.is_dir():
            continue
        for jsonl_file in project_dir.glob("*.jsonl"):
            try:
                # 读取第一条获取会话信息
                with open(jsonl_file, 'r', encoding='utf-8') as f:
                    first_line = f.readline()
                    if first_line:
                        data = json.loads(first_line)
                        # 从文件名提取会话 ID
                        session_id = jsonl_file.stem
                        sessions.append({
                            "id": session_id,
                            "title": f"Claude Code - {project_dir.name}",
                            "directory": str(project_dir.name),
                            "time_created": str(jsonl_file.stat().st_ctime),
                            "time_updated": str(jsonl_file.stat().st_mtime),
                            "message_count": sum(1 for _ in open(jsonl_file, encoding='utf-8', errors='ignore')),
                            "source": "claude_code"
                        })
            except (json.JSONDecodeError, OSError):
                continue
    
    return sessions


def get_codex_session_messages(session_id: str) -> List[dict]:
    """获取 Codex 会话的消息"""
    sessions_path = CONFIG[DataSource.CODEX]["sessions_path"]
    messages = []
    
    if not sessions_path.exists():
        return messages
    
    # 查找对应的 JSONL 文件（文件名格式: rollout-YYYY-MM-DDTHH-MM-SS-session_id.jsonl）
    for year_dir in sessions_path.iterdir():
        if not year_dir.is_dir():
            continue
        for month_dir in year_dir.iterdir():
            if not month_dir.is_dir():
                continue
            for day_dir in month_dir.iterdir():
                if not day_dir.is_dir():
                    continue
                for jsonl_file in day_dir.glob("rollout-*.jsonl"):
                    # 检查文件名是否包含 session_id
                    if session_id not in jsonl_file.name:
                        continue
                    try:
                        with open(jsonl_file, 'r', encoding='utf-8', errors='ignore') as f:
                            for line in f:
                                if not line.strip():
                                    continue
                                msg_data = json.loads(line)
                                msg_type = msg_data.get("type")
                                
                                # Codex 消息类型是 response_item
                                if msg_type == "response_item":
                                    payload = msg_data.get("payload", {})
                                    if payload.get("type") == "message":
                                        role = payload.get("role", "unknown")
                                        content_list = payload.get("content", [])
                                        # 提取文本内容
                                        content = ""
                                        for item in content_list:
                                            if item.get("type") == "input_text":
                                                content += item.get("text", "")
                                            elif item.get("type") == "output_text":
                                                content += item.get("text", "")
                                        messages.append({
                                            "id": msg_data.get("id", ""),
                                            "role": role,
                                            "content": content,
                                            "time_created": msg_data.get("timestamp", ""),
                                        })
                    except (json.JSONDecodeError, OSError):
                        continue
    
    return messages


def get_claude_code_session_messages(session_id: str) -> List[dict]:
    """获取 Claude Code 会话的消息"""
    projects_path = CONFIG[DataSource.CLAUDE_CODE]["projects_path"]
    messages = []
    
    if not projects_path.exists():
        return messages
    
    # 查找对应的 JSONL 文件
    for project_dir in projects_path.iterdir():
        if not project_dir.is_dir():
            continue
        for jsonl_file in project_dir.glob(f"{session_id}.jsonl"):
            try:
                with open(jsonl_file, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        if not line.strip():
                            continue
                        data = json.loads(line)
                        
                        # 跳过 file-history-snapshot 类型
                        if data.get("type") == "file-history-snapshot":
                            continue
                        
                        # Claude Code 的消息格式：type 是 user 或 assistant
                        msg_type = data.get("type")
                        if msg_type in ["user", "assistant"]:
                            msg = data.get("message", {})
                            content_list = msg.get("content", [])
                            
                            # 提取文本内容
                            content = ""
                            if isinstance(content_list, list):
                                for item in content_list:
                                    if isinstance(item, dict):
                                        if item.get("type") == "text":
                                            content += item.get("text", "")
                            elif isinstance(content_list, str):
                                content = content_list
                            
                            messages.append({
                                "id": data.get("uuid", ""),
                                "role": msg.get("role", msg_type),
                                "content": content,
                                "time_created": data.get("timestamp", ""),
                            })
            except (json.JSONDecodeError, OSError):
                continue
    
    return messages


def get_all_sessions(source: Optional[DataSource] = None) -> List[dict]:
    """获取所有平台的会话列表"""
    all_sessions = []
    
    # OpenCode
    if (source is None or source == DataSource.OPENCODE) and is_opencode_available():
        with get_opencode_db() as conn:
            cur = conn.execute("""
                SELECT 
                    s.id,
                    s.title,
                    s.directory,
                    s.time_created,
                    s.time_updated,
                    COUNT(m.id) as message_count
                FROM session s
                LEFT JOIN message m ON s.id = m.session_id
                WHERE s.parent_id IS NULL AND s.title NOT LIKE '%subagent%'
                GROUP BY s.id
                ORDER BY s.time_updated DESC
            """)
            for row in cur.fetchall():
                all_sessions.append({
                    "id": row["id"],
                    "title": row["title"],
                    "directory": row["directory"],
                    "time_created": str(row["time_created"]),
                    "time_updated": str(row["time_updated"]),
                    "message_count": row["message_count"],
                    "source": "opencode"
                })
    
    # Codex
    if source is None or source == DataSource.CODEX:
        all_sessions.extend(get_codex_sessions())
    
    # Claude Code
    if source is None or source == DataSource.CLAUDE_CODE:
        all_sessions.extend(get_claude_code_sessions())
    
    # 按更新时间排序
    all_sessions.sort(key=lambda x: x.get("time_updated", ""), reverse=True)
    return all_sessions


def parse_timestamp(value: Any) -> Optional[datetime]:
    """兼容 Unix 秒/毫秒时间戳与 ISO 时间字符串，统一转成本地时间。"""
    if value in (None, ""):
        return None

    if isinstance(value, datetime):
        parsed = value
    else:
        stripped = str(value).strip()
        if not stripped:
            return None

        try:
            parsed = datetime.fromisoformat(stripped.replace("Z", "+00:00"))
        except ValueError:
            try:
                numeric_value = float(stripped)
            except ValueError:
                return None

            timestamp_seconds = numeric_value / 1000 if abs(numeric_value) >= 1_000_000_000_000 else numeric_value
            return datetime.fromtimestamp(timestamp_seconds)

    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)

    return parsed


def format_timestamp(ts: Any) -> str:
    """统一格式化不同来源的时间字段，输出 YYYY-MM-DD HH:MM:SS。"""
    parsed = parse_timestamp(ts)
    if not parsed:
        return ""
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def normalize_session_summary(session: Optional[dict]) -> Optional[dict]:
    """把文件型会话摘要中的时间字段规范成统一展示格式。"""
    if not session:
        return None

    normalized = dict(session)
    normalized["time_created"] = format_timestamp(normalized.get("time_created"))
    normalized["time_updated"] = format_timestamp(normalized.get("time_updated"))
    return normalized


# ==================== API 路由 ====================

@app.get("/api/sources")
def get_sources():
    """获取可用的数据源列表"""
    return [
        {"id": "opencode", "name": "OpenCode", "icon": "🟣"},
        {"id": "codex", "name": "Codex", "icon": "🔵"},
        {"id": "claude_code", "name": "Claude Code", "icon": "🟤"},
    ]


@app.get("/api/projects", response_model=List[Project])
def get_projects():
    """获取所有项目及其会话数量"""
    if not is_opencode_available():
        return []

    with get_opencode_db() as conn:
        cur = conn.execute("""
            SELECT 
                p.id,
                p.name,
                p.worktree,
                COUNT(DISTINCT s.id) as session_count
            FROM project p
            LEFT JOIN session s ON p.id = s.project_id 
                AND s.parent_id IS NULL 
                AND s.title NOT LIKE '%subagent%'
            GROUP BY p.id
            HAVING session_count > 0
            ORDER BY session_count DESC
        """)
        return [
            Project(
                id=row["id"],
                name=row["name"] or Path(row["worktree"]).name,
                worktree=row["worktree"],
                session_count=row["session_count"]
            )
            for row in cur.fetchall()
        ]


@app.get("/api/sessions", response_model=List[dict])
def get_sessions(
    source: Optional[DataSource] = None,
    project_id: Optional[str] = None,
    sort_by: str = Query("time_updated", pattern="^(time_created|time_updated)$"),
    order: str = Query("desc", pattern="^(asc|desc)$")
):
    """获取会话列表（支持多数据源切换）"""
    # 如果指定了 source，使用统一的会话获取函数
    if source:
        sessions = get_all_sessions(source)
        reverse = order == "desc"
        sessions.sort(key=lambda x: x.get(sort_by, ""), reverse=reverse)
        return [normalize_session_summary(session) for session in sessions]
    
    # 否则使用原有的 OpenCode 逻辑
    if not is_opencode_available():
        return []

    with get_opencode_db() as conn:
        sql = """
            SELECT 
                s.id,
                s.title,
                s.directory,
                s.time_created,
                s.time_updated,
                s.summary_additions,
                s.summary_deletions,
                COUNT(m.id) as message_count
            FROM session s
            LEFT JOIN message m ON s.id = m.session_id
            WHERE s.parent_id IS NULL 
              AND s.title NOT LIKE '%subagent%'
        """
        params = []
        
        if project_id:
            sql += " AND s.project_id = ?"
            params.append(project_id)
        
        sql += f" GROUP BY s.id ORDER BY s.{sort_by} {order.upper()}"
        
        cur = conn.execute(sql, params)
        return [
            SessionSummary(
                id=row["id"],
                title=row["title"],
                directory=row["directory"],
                time_created=format_timestamp(row["time_created"]),
                time_updated=format_timestamp(row["time_updated"]),
                message_count=row["message_count"],
                summary_additions=row["summary_additions"],
                summary_deletions=row["summary_deletions"]
            )
            for row in cur.fetchall()
        ]


@app.get("/api/sessions/{session_id}/messages", response_model=List[Message])
def get_session_messages(session_id: str, source: Optional[DataSource] = None):
    """获取会话的所有消息（支持多数据源）"""
    
    # 如果指定了 source，使用对应的消息获取函数
    if source == DataSource.CODEX:
        raw_messages = get_codex_session_messages(session_id)
        return [
            Message(
                id=m["id"],
                role=m["role"],
                time_created=format_timestamp(m.get("time_created")),
                content=m.get("content"),
                tokens_input=None,
                tokens_output=None,
                parts=[{"type": "text", "text": m.get("content", "")}]
            )
            for m in raw_messages
        ]
    
    if source == DataSource.CLAUDE_CODE:
        raw_messages = get_claude_code_session_messages(session_id)
        return [
            Message(
                id=m["id"],
                role=m["role"],
                time_created=format_timestamp(m.get("time_created")),
                content=m.get("content"),
                tokens_input=None,
                tokens_output=None,
                parts=[{"type": "text", "text": m.get("content", "")}]
            )
            for m in raw_messages
        ]
    
    # 默认使用 OpenCode
    if not is_opencode_available():
        return []

    with get_opencode_db() as conn:
        # 获取消息
        cur = conn.execute("""
            SELECT id, time_created, data
            FROM message
            WHERE session_id = ?
            ORDER BY time_created
        """, (session_id,))
        
        messages = []
        for row in cur.fetchall():
            data = json.loads(row["data"])
            
            # 获取消息的 parts
            parts_cur = conn.execute("""
                SELECT id, data, time_created
                FROM part
                WHERE message_id = ?
                ORDER BY time_created
            """, (row["id"],))
            
            parts = []
            content_pieces = []
            
            for part_row in parts_cur.fetchall():
                part_data = json.loads(part_row["data"])
                parts.append(part_data)
                
                # 提取文本内容
                if part_data.get("type") == "text":
                    content_pieces.append(part_data.get("text", ""))
                elif part_data.get("type") == "tool":
                    tool_name = part_data.get("tool", "unknown")
                    tool_input = part_data.get("input", {})
                    tool_output = part_data.get("output", "")
                    
                    # 格式化工具调用
                    tool_text = f"\n**Tool: {tool_name}**\n"
                    if isinstance(tool_input, dict):
                        for k, v in tool_input.items():
                            if k != "description" and v:
                                tool_text += f"- {k}: `{str(v)[:100]}{'...' if len(str(v)) > 100 else ''}`\n"
                    if tool_output:
                        output_preview = str(tool_output)[:500]
                        if len(str(tool_output)) > 500:
                            output_preview += "..."
                        tool_text += f"\n```\n{output_preview}\n```\n"
                    content_pieces.append(tool_text)
            
            tokens = data.get("tokens", {})
            messages.append(Message(
                id=row["id"],
                role=data.get("role", "unknown"),
                time_created=format_timestamp(row["time_created"]),
                content="\n".join(content_pieces) if content_pieces else None,
                tokens_input=tokens.get("input"),
                tokens_output=tokens.get("output"),
                parts=parts
            ))
        
        return messages


@app.get("/api/search", response_model=List[SearchResult])
def search_sessions(
    source: Optional[DataSource] = None,
    q: str = Query(..., min_length=1),
    limit: int = Query(50, le=200)
):
    """全局搜索消息内容（搜索 part 表获取实际文本）"""
    if source == DataSource.CODEX:
        return search_file_sessions(DataSource.CODEX, q, limit)

    if source == DataSource.CLAUDE_CODE:
        return search_file_sessions(DataSource.CLAUDE_CODE, q, limit)

    if source == DataSource.OPENCODE:
        return search_opencode_sessions(q, limit)

    # 未指定 source 时聚合所有可用数据源，但仍以 limit 作为最终上限。
    results = search_opencode_sessions(q, limit)
    remaining = max(0, limit - len(results))
    if remaining:
        results.extend(search_file_sessions(DataSource.CODEX, q, remaining))
    remaining = max(0, limit - len(results))
    if remaining:
        results.extend(search_file_sessions(DataSource.CLAUDE_CODE, q, remaining))
    return results[:limit]


@app.get("/api/sessions/{session_id}/export")
def export_session(session_id: str, source: Optional[DataSource] = None):
    """导出会话为 Markdown"""
    current_source = source or DataSource.OPENCODE

    if current_source == DataSource.OPENCODE:
        if not is_opencode_available():
            raise HTTPException(status_code=404, detail="OpenCode database not found")

        with get_opencode_db() as conn:
            cur = conn.execute("""
                SELECT id, title, directory, time_created, time_updated
                FROM session WHERE id = ?
            """, (session_id,))
            session = cur.fetchone()

            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

            session_meta = {
                "id": session["id"],
                "title": session["title"],
                "directory": session["directory"],
                "time_created": format_timestamp(session["time_created"]),
                "time_updated": format_timestamp(session["time_updated"]),
            }
    else:
        session_meta = get_file_session_summary(current_source, session_id)
        if not session_meta:
            raise HTTPException(status_code=404, detail="Session not found")

    messages = get_session_messages(session_id, current_source)

    md_lines = [
        f"# {session_meta['title']}",
        "",
        f"- **Session ID**: `{session_meta['id']}`",
        f"- **Directory**: `{session_meta['directory']}`",
        f"- **Created**: {session_meta['time_created']}",
        f"- **Updated**: {session_meta['time_updated']}",
        "",
        "---",
        ""
    ]

    for msg in messages:
        role_icon = "👤" if msg.role == "user" else "🤖"
        md_lines.append(f"## {role_icon} {msg.role.upper()} ({msg.time_created})")
        md_lines.append("")
        if msg.content:
            md_lines.append(msg.content)
        md_lines.append("")
        if msg.tokens_input or msg.tokens_output:
            md_lines.append(f"*Tokens: in={msg.tokens_input}, out={msg.tokens_output}*")
        md_lines.append("")
        md_lines.append("---")
        md_lines.append("")

    return PlainTextResponse(
        content="\n".join(md_lines),
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="{session_id}.md"'
        }
    )


# ==================== 前端静态文件 ====================

# 挂载静态文件目录
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=HTMLResponse)
def index():
    """返回前端页面"""
    index_file = Path(__file__).parent / "static" / "index.html"
    if index_file.exists():
        return index_file.read_text(encoding="utf-8")
    return """
    <html>
    <head><title>OpenCode Viewer</title></head>
    <body>
        <h1>OpenCode Session Viewer</h1>
        <p>Please create static/index.html</p>
        <p>API endpoints:</p>
        <ul>
            <li><a href="/api/projects">/api/projects</a></li>
            <li><a href="/api/sessions">/api/sessions</a></li>
            <li>/api/sessions/{id}/messages</li>
            <li>/api/search?q=keyword</li>
            <li>/api/sessions/{id}/export</li>
        </ul>
    </body>
    </html>
    """


if __name__ == "__main__":
    import uvicorn
    reload_enabled = os.getenv("OPENCODE_VIEWER_RELOAD", "1") not in {"0", "false", "False"}
    server_host, server_port, server_url = resolve_server_config()
    print_source_path_status(DataSource.OPENCODE, "OpenCode DB", ["OPENCODE_DB_PATH", "OPENCODE_HOME"], "db_path")
    print_source_path_status(DataSource.CODEX, "Codex Sessions", ["CODEX_SESSIONS_PATH", "CODEX_HOME"], "sessions_path")
    print_source_path_status(DataSource.CLAUDE_CODE, "Claude Code Projects", ["CLAUDE_PROJECTS_PATH", "CLAUDE_HOME"], "projects_path")
    print(f"Starting server at {server_url} (reload={'on' if reload_enabled else 'off'})")
    if should_open_browser():
        schedule_browser_open(server_url)
    uvicorn.run("app:app", host=server_host, port=server_port, reload=reload_enabled)
