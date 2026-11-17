# -*- coding: utf-8 -*-
"""术语词库：内置常用 Windows/开发术语，支持外部 glossary.json 覆盖/扩充。

查找顺序：exe/脚本同目录 glossary.json → %APPDATA%\\SelectTrans\\glossary.json → 内置表。
外部文件是普通 JSON（术语: 中文），可直接编辑保存即生效。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

# 内置术语表（也是 glossary.json 的初始内容）
DEFAULT_GLOSSARY = {
    # ---- Windows / 注册表 / 系统 ----
    "HKCU Run": "注册表 Run 键（当前用户开机自启动项）",
    "HKLM Run": "注册表 Run 键（所有用户开机自启动项）",
    "Run key": "注册表 Run 键（开机自启动项）",
    "HKCU": "HKEY_CURRENT_USER（当前用户注册表根键）",
    "HKLM": "HKEY_LOCAL_MACHINE（本机注册表根键）",
    "HKEY_CURRENT_USER": "当前用户注册表根键",
    "HKEY_LOCAL_MACHINE": "本机注册表根键",
    "registry": "注册表",
    "autostart": "自启动",
    "auto start": "自动启动",
    "startup": "启动项；开机自启",
    "startup folder": "启动文件夹（开机自启）",
    "tray": "系统托盘（通知区）",
    "system tray": "系统托盘（右下角通知区）",
    "tray icon": "托盘图标",
    "taskbar": "任务栏",
    "tooltip": "悬浮提示",
    "hotkey": "热键（快捷键）",
    "shortcut": "快捷方式",
    "clipboard": "剪贴板",
    "screenshot": "截图",
    "exe": "可执行文件（.exe）",
    "dll": "动态链接库（.dll）",
    "console": "控制台（命令行窗口）",
    "noconsole": "无控制台模式（启动时不显示命令行窗口）",
    "onefile": "单文件打包模式",
    "onedir": "文件夹打包模式",
    "portable": "绿色版（免安装）",
    "installer": "安装包",
    "UAC": "用户账户控制",
    "admin": "管理员",
    "firewall": "防火墙",
    "antivirus": "杀毒软件",
    "permission denied": "权限被拒绝",
    "args": "参数",
    "argv": "命令行参数",
    "stdout": "标准输出",
    "stderr": "标准错误输出",
    "stdin": "标准输入",
    "env": "环境变量",
    "environment variable": "环境变量",
    "PATH": "路径（环境变量 PATH 为可执行文件搜索路径）",
    "symlink": "符号链接",
    "zip": "压缩包",
    "unzip": "解压",
    "backup": "备份",
    "restore": "还原",
    # ---- 编程 / 开发 ----
    "bug": "缺陷（Bug）",
    "feature": "功能",
    "release": "发行版",
    "build": "构建",
    "compile": "编译",
    "runtime": "运行时",
    "framework": "框架",
    "library": "库",
    "repo": "代码仓库",
    "commit": "提交",
    "branch": "分支",
    "merge": "合并",
    "pull request": "拉取请求（PR）",
    "push": "推送",
    "pull": "拉取",
    "debug": "调试",
    "deploy": "部署",
    "server": "服务器",
    "client": "客户端",
    "backend": "后端",
    "frontend": "前端",
    "api": "应用程序接口（API）",
    "sdk": "软件开发工具包（SDK）",
    "cli": "命令行界面",
    "gui": "图形界面",
    "ide": "集成开发环境",
    "url": "网址",
    "json": "JSON 数据格式",
    "yaml": "YAML 配置格式",
    "csv": "逗号分隔表格文件",
    "regex": "正则表达式",
    "timestamp": "时间戳",
    "cache": "缓存",
    "cookie": "Cookie（网站凭据）",
    "token": "令牌（身份凭据）",
    "auth": "认证",
    "login": "登录",
    "logout": "退出登录",
    "password": "密码",
    "encryption": "加密",
    "decrypt": "解密",
    "hash": "哈希（散列）",
    "md5": "MD5 哈希算法",
    "sha256": "SHA-256 哈希算法",
    "thread": "线程",
    "process": "进程",
    "async": "异步",
    "sync": "同步",
    "callback": "回调",
    "hook": "钩子",
    "debounce": "防抖",
    "throttle": "节流",
    "queue": "队列",
    "stack": "栈",
    "array": "数组",
    "dict": "字典（键值对）",
    "dictionary": "字典",
    "string": "字符串",
    "integer": "整数",
    "boolean": "布尔值",
    "float": "浮点数",
    "null": "空值",
    "undefined": "未定义",
    "exception": "异常",
    "error handling": "错误处理",
    "refactor": "重构",
    "deprecated": "已废弃",
    "legacy": "遗留（旧代码/旧系统）",
    "open source": "开源",
    "license": "许可证",
    "dependency": "依赖",
    "package": "软件包",
    "install": "安装",
    "uninstall": "卸载",
    "update": "更新",
    "upgrade": "升级",
    "rollback": "回滚",
    "compatibility": "兼容性",
    "cross-platform": "跨平台",
    "multi-threaded": "多线程",
    "single instance": "单实例（只允许运行一个）",
    "mutex": "互斥锁",
    "semaphore": "信号量",
    "deadlock": "死锁",
    "memory leak": "内存泄漏",
    "crash": "崩溃",
    "stack overflow": "栈溢出",
    "traceback": "调用栈（报错堆栈）",
    "log": "日志",
    "breakpoint": "断点（调试/布局）",
    "profiler": "性能分析器",
    "benchmark": "基准测试",
    "unit test": "单元测试",
    "test case": "测试用例",
    "coverage": "测试覆盖率",
    "lint": "代码检查（Lint）",
    "format": "格式化",
    "code review": "代码评审",
    "fork": "复刻（仓库分叉）",
    "issue": "问题（Issue）",
    "patch": "补丁",
    "workaround": "权宜之计（临时规避方案）",
    "hotfix": "热修复",
    "changelog": "更新日志",
    "readme": "自述文件",
    "docs": "文档",
    "tutorial": "教程",
    "example": "示例",
    "snippet": "代码片段",
    "boilerplate": "样板代码",
    "scaffold": "脚手架",
    "prototype": "原型",
    "mock": "模拟（Mock）",
    "stub": "桩（Stub）",
    "endpoint": "接口端点",
    "webhook": "回调钩子（Webhook）",
    "rest": "REST 风格接口",
    "graphql": "GraphQL 查询语言",
    "websocket": "WebSocket 长连接",
    "http": "超文本传输协议",
    "https": "加密的超文本传输协议",
    "tcp": "传输控制协议",
    "udp": "用户数据报协议",
    "dns": "域名系统",
    "ip": "IP 地址",
    "port": "端口",
    "proxy": "代理",
    "vpn": "虚拟专用网络",
    "cdn": "内容分发网络",
    "ssh": "安全外壳协议（SSH）",
    "ftp": "文件传输协议",
    "browser": "浏览器",
    "extension": "扩展（插件）",
    "plugin": "插件",
    "theme": "主题",
    "dark mode": "深色模式",
    "light mode": "浅色模式",
    "widget": "组件（小部件）",
    "modal": "模态框",
    "popup": "弹窗",
    "dropdown": "下拉菜单",
    "checkbox": "复选框",
    "toggle": "开关",
    "slider": "滑块",
    "scroll": "滚动",
    "hover": "悬停",
    "drag": "拖拽",
    "resize": "调整尺寸",
    "viewport": "视口",
    "responsive": "响应式",
    "layout": "布局",
    "padding": "内边距",
    "margin": "外边距",
    "border": "边框",
    "shadow": "阴影",
    "radius": "圆角",
    "opacity": "不透明度",
    "gradient": "渐变",
    "animation": "动画",
    "transition": "过渡",
    "icon": "图标",
    "font": "字体",
    # ---- 常用 CLI 参数 ----
    "flag": "标志（开关参数）",
    "option": "选项",
    "default": "默认值",
    "config": "配置",
    "settings": "设置",
    "workspace": "工作区",
    "folder": "文件夹",
    "directory": "目录",
    "filename": "文件名",
}

MAX_TERMS = 4          # 最多按术语匹配的词数
MAX_LEN = 60           # 术语最长字符数

_lookup: dict[str, str] | None = None


def _norm(s: str) -> str:
    return " ".join((s or "").split()).casefold()


def _load_lookup() -> dict[str, str]:
    merged = {_norm(k): v for k, v in DEFAULT_GLOSSARY.items()}
    candidates = []
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    candidates.append(base / "glossary.json")
    candidates.append(Path(os.environ.get("APPDATA", tempfile.gettempdir())) / "SelectTrans" / "glossary.json")
    for p in candidates:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                merged.update({_norm(k): str(v) for k, v in data.items() if k and v})
        except Exception:
            pass
    return merged


def lookup(text: str) -> str | None:
    """命中术语词库返回中文释义，否则 None。仅对短语（≤4 词）生效。"""
    global _lookup
    if _lookup is None:
        _lookup = _load_lookup()
    t = (text or "").strip()
    if not t or len(t) > MAX_LEN or len(t.split()) > MAX_TERMS:
        return None
    return _lookup.get(_norm(t))


def dump_default_json(path: Path) -> None:
    """把内置词库导出为 glossary.json（供用户编辑）。"""
    path.write_text(
        json.dumps(DEFAULT_GLOSSARY, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
