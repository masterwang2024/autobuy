# autobuy

DJI 多账号自动加购（Tkinter GUI + Playwright）重构版，支持：
- 在 App 内配置账号（不依赖本地账号文档）
- 在 App 内配置多个任务（URL、版本、模式、账号分配）
- 支持执行“选中任务”或“全部启用任务”
- 多账号并发执行（线程池限流）
- 基本信息持久化（账号、任务、执行参数）
- 可停止任务、执行统计、日志落盘

## 项目结构

- `main.py`：GUI 启动入口
- `dji_autobuy/models.py`：数据模型与配置
- `dji_autobuy/accounts.py`：账号文档解析
- `dji_autobuy/scraper.py`：商品版本与库存探测
- `dji_autobuy/worker.py`：自动化任务执行逻辑（当前含示例占位）
- `dji_autobuy/service.py`：线程池调度和停止控制
- `dji_autobuy/settings_store.py`：本地配置读写
- `dji_autobuy/run_logger.py`：任务日志文件输出
- `dji_autobuy/gui.py`：图形界面与线程调度

## 运行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
python main.py
```

## 打包为 macOS `.app`

```bash
./build_macos.sh
```

构建完成后产物：
- `dist/DJI_Autobuy.app`

## Git 初始化（本地）

```bash
git init
git add .
git commit -m "feat: initial autobuy refactor and mac app packaging"
```

## 说明

`worker.py` 中“登录、选配、加购”的业务细节目前保留为示例占位，需替换为你的稳定 `Worker.run` 实现。

## 基本信息存放

- 配置文件：`~/.autobuy/settings.json`
- 运行日志：项目目录下 `logs/run_YYYYMMDD_HHMMSS.log`

## 后续 UAT 变更规则

- 本次为初始版本，不单独产出补丁。
- 从下一次需求新增/删除/问题修复开始，每次变更都同时产出一个 patch 文件，存放在 `patches/` 目录。
- 需求/问题时间线日志维护在：`docs/AUTOBUY_full_conversation_log.txt`（当前不包含 Codex 提交时间轴段落）。
