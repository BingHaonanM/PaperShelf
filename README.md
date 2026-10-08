# PaperShelf v1.2.2 · Windows / Mac 双击启动版

PaperShelf 是一个轻量级、本地优先的文献管理网页。支持多个独立课题文献库、BibTeX 导入、PDF 阅读、检索、阅读状态和独立 Markdown 笔记。本项目不需要账号、云服务器或第三方 Python 库。支持 Windows 10/11 和 macOS；需要 **Python 3.9 或更新版本**。

**公开版说明**：本安装包只包含程序文件与三篇**虚构**的 LLM / NN / Machine Learning 示例 BibTeX 文献，不含真实论文全文、私人笔记和个人文献库。演示文献不能作为真实学术引用。

## Windows 安装与启动

1. 在 https://www.python.org/downloads/windows/ 安装 Python 3.9+；安装时建议勾选 **Add python.exe to PATH**。如果已安装，可在 PowerShell 输入 `py -3 --version` 检查。
2. 下载 `PaperShelf-v1.2.2-Mac-Windows-Start.zip`，**完整解压**到任意位置，打开解压出的 `PaperShelf` 文件夹。不要在压缩包预览界面中直接执行脚本。
3. **双击 `Start.bat`**。启动窗口会显示本地访问地址，并在服务就绪后自动打开浏览器。端口默认是 `8765`；若被占用，则会在 `8766–8775` 中寻找空闲端口。
4. 在网页右上角导入 `demo.bib` 测试功能，或导入自己的 BibTeX 文件。
5. **停止服务**：切回启动的黑色命令行窗口，按 `Ctrl+C`；若 Windows 提示 `Terminate batch job (Y/N)?`，输入 `Y`。

> `Start.bat` 需要与 `launcher.py`、`app.py` 保存在**同一个 PaperShelf 文件夹**。脚本会自动定位所在目录，可放在带空格的目录中。Python 不存在或版本过低时会显示安装提示，不会偷偷安装其他软件。

## Mac 安装与启动

1. 确保已安装 Python 3.9+，在终端输入 `python3 --version` 检查。
2. 解压同一个 ZIP，双击 `PaperShelf/Start.command`。首次出现“没有权限”时，进入该文件夹执行 `chmod +x Start.command`，再双击。
3. 浏览器会自动打开网页；终端窗口按 `Control+C` 停止。

macOS 从网络下载脚本可能触发安全提示。确认来源可信并检查脚本内容后，按系统安全设置授权，不要随意关闭系统保护。

## 已安装旧版：升级但保留数据

更新前关闭原有 PaperShelf 服务，并备份原项目中的 `data/`。**本 ZIP 不包含 `data/`，覆盖程序文件不会删除旧数据。** 在 Mac 上如果你的安装目录是 `~/Documents/PaperShelf`，可直接执行：

```bash
cd ~/Documents/PaperShelf
[ ! -d data ] || cp -R data "../PaperShelf-data-backup-$(date +%Y%m%d-%H%M%S)"
unzip -o ~/Downloads/PaperShelf-v1.2.2-Mac-Windows-Start.zip -d ~/Documents
cd ~/Documents/PaperShelf
./Start.command
```

在 Windows 上，先复制原目录的 `data` 文件夹作为备份，再把新版 ZIP 中的**程序文件**合并覆盖到旧目录；不要删除或覆盖原来的 `data/`。注意老版本的数据可能包含真实研究方向，升级并不会自动匿名化这些内容。

## 用于 GitHub / 视频录制：干净的公开演示

录屏前请把 ZIP **解压到全新、独立的文件夹**，不要使用保存真实论文和笔记的原安装目录。首次运行时会创建空数据目录。在网页中建立 `LLM`、`NN`、`Machine Learning` 等示例文献库，然后选择 `demo.bib` 导入三篇虚构论文。

发布源码时不要包含 `data/`、真实 PDF 或个人笔记，项目已附 `.gitignore`，用于 Git 提交时排除私人数据。打包或浏览器手动上传 GitHub 时仍要检查文件列表。

## 功能

- 多文献库：新建库、切换库、跨库移动文献；同一论文在不同库里可有独立笔记。
- BibTeX：导入时选择文献库；同库 DOI 或题名＋年份去重，重新导入不会清空已有笔记。
- PDF：上传并关联本地 PDF 后可在网页预览；没有本地文件时可通过 DOI 跳转出版商页面。
- 笔记：Markdown 编辑与保存，保留在本地 `data/notes/`。
- 搜索：标题、作者、年份、标签、阅读状态等基本筛选。

## 文件结构

```text
PaperShelf/
├── Start.bat        # Windows 双击启动
├── launcher.py      # Windows 启动逻辑：寻找可用端口、打开浏览器
├── Start.command    # Mac 双击启动
├── app.py           # 本地服务
├── index.html       # 网页界面
├── style.css
├── app.js
├── demo.bib         # 虚构的通用 AI/ML 示例
├── .gitignore
└── data/            # 首次运行创建；不要提交 GitHub
    ├── library.json
    ├── pdfs/
    └── notes/
```

## 说明与限制

- 数据全部保存在当前安装目录的 `data/`，网页服务仅绑定 `127.0.0.1`，不上传个人文献数据。请定期备份 `data/`。
- ZIP 中的代码适用于 Windows / Mac，但系统仍需要安装 Python；目前未制作 `.exe` / `.app` 原生安装包。
- 不提供数据库授权绕过、付费全文自动下载、云同步、Word 引用插件或高级 PDF 标注。
- `demo.bib` 中的三篇论文均为虚构案例，不得用于学术引用。
- 技术上可直接运行 `python app.py`（Windows）或 `python3 app.py`（Mac），然后访问 http://127.0.0.1:8765 。也可使用 `--port 8766` 指定端口。
