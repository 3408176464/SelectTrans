# 划词翻译 SelectTrans

> Windows 划词翻译工具：选中任意文字，自动弹出翻译卡片。轻量、免费、可扩充词库。

## 功能特性

- **划词即译**：鼠标拖选 / 双击选词，翻译卡片自动弹在光标旁
- **中英互译**：自动识别方向；英文单词给词典释义，句子走机器翻译
- **术语词库**：内置 2700+ 计算机/Windows 术语（`HKCU Run` → 注册表 Run 键），支持自行扩充
- **轻量低占用**：单进程常驻托盘，闲置工作集约 10MB、CPU≈0
- **托盘常驻**：开机自启（可关）、关闭卡片不退出、单实例
- **现代卡片 UI**：圆角阴影、渐入动效、按内容自适应宽高

## 安装

下载 [Releases](../../releases) 中的 `SelectTransSetup.exe`，双击安装： 

- 可选择安装位置
- 可选：开机自启 / 最小化到托盘 / 桌面快捷方式
- 升级不会覆盖你编辑过的词库

## 使用

| 操作 | 说明 |
|---|---|
| 选中文字 | 自动弹出翻译（拖选或双击） |
| `Ctrl+Alt+Y` | 手动翻译当前选中 |
| `Ctrl+Alt+S` | 自动划词开/关 |
| `Ctrl+Alt+Q` | 退出 |
| 托盘右键 | 自动划词 / 开机自启 / 退出 |

## 词库扩充

编辑 exe 同目录的 `glossary.json`（普通 JSON，`英文: 中文`），保存即生效： 

```json
{
  "pull request": "拉取请求（PR）",
  "HKCU Run": "注册表 Run 键（当前用户开机自启动项）"
}
```

匹配规则：≤4 词的短语优先查词库；单词先走词典释义，译不出时词库兜底。

## 从源码构建

```bash
pip install -r requirements.txt
python build.py            # 产出 dist/SelectTrans/（文件夹版）
# 制作安装包（需要 Inno Setup 6）：
ISCC.exe SelectTrans.iss   # 产出 dist/SelectTransSetup.exe
```

> 离线翻译模型（`offline_models/translate-en_zh.argosmodel`，约 70MB）不入库；构建时缺失会提示下载来源（HuggingFace `shethjenil/argostranslate`），解包后 build.py 自动打进安装包。

## 实现说明

- 翻译引擎：webfanyi（主，含词典释义）→ MyMemory（备）→ 术语词库
- 弹窗为 PySide6 自绘（圆角/阴影/渐入），取词走「模拟 Ctrl+C + 剪贴板还原」
- 高 DPI 下鼠标物理坐标需换算为 Qt 逻辑坐标（坑记录在案）

## 免责声明

**仅供学习交流使用**，请勿用于商业用途；如有侵权请联系移除。使用中产生的一切后果由使用者自行承担。

## 致谢与许可

- 代码：MIT
- 词库数据汇编自：
  - [Sakura4036/program-vocabulary](https://github.com/Sakura4036/program-vocabulary)（MIT）
  - [jilaokang/coder-dictionary](https://github.com/jilaokang/coder-dictionary)
  - [ziqiangxu/chinese-glossary](https://github.com/ziqiangxu/chinese-glossary)（CC BY-SA）
- 安装器：[Inno Setup](https://jrsoftware.org/isinfo.php)；中文语言包来自 [jrsoftware/issrc](https://github.com/jrsoftware/issrc)
