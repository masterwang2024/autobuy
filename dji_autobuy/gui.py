from __future__ import annotations

import queue
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .accounts import read_accounts_from_docx
from .models import JobConfig, WorkerResult
from .run_logger import RunLogger
from .scraper import preload_product
from .service import AutobuyService
from .settings_store import AppSettings, load_settings, save_settings


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("DJI 多账号自动加购")
        self.geometry("1000x780")

        self.service = AutobuyService()
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.event_queue: queue.Queue[tuple[str, object]] = queue.Queue()

        self.success_count = 0
        self.failed_count = 0
        self.cancelled_count = 0
        self.total_count = 0
        self.run_logger: RunLogger | None = None

        self._build_ui()
        self._load_settings_into_ui()
        self._refresh_account_count()
        self.after(100, self._drain_queues)

    def _build_ui(self) -> None:
        account_frame = ttk.LabelFrame(self, text="账号文件")
        account_frame.pack(fill=tk.X, padx=12, pady=6)

        default_docx = Path(__file__).resolve().parent.parent / "账号信息.docx"
        self.var_docx = tk.StringVar(value=str(default_docx))
        ttk.Entry(account_frame, textvariable=self.var_docx, width=76).pack(side=tk.LEFT, padx=6)
        ttk.Button(account_frame, text="选择", command=self._pick_docx).pack(side=tk.LEFT)
        self.lbl_count = ttk.Label(account_frame, text="未读取")
        self.lbl_count.pack(side=tk.LEFT, padx=8)

        product_frame = ttk.LabelFrame(self, text="商品")
        product_frame.pack(fill=tk.X, padx=12, pady=6)

        self.var_url = tk.StringVar()
        ttk.Label(product_frame, text="URL:").pack(side=tk.LEFT)
        ttk.Entry(product_frame, textvariable=self.var_url, width=72).pack(side=tk.LEFT, padx=6)
        ttk.Button(product_frame, text="预加载", command=self._preload).pack(side=tk.LEFT, padx=4)
        ttk.Button(product_frame, text="保存信息", command=self._save_settings).pack(side=tk.LEFT, padx=4)

        version_frame = ttk.LabelFrame(self, text="版本与库存")
        version_frame.pack(fill=tk.X, padx=12, pady=6)

        self.cmb_version = ttk.Combobox(version_frame, values=[], width=30, state="readonly")
        self.cmb_version.pack(side=tk.LEFT, padx=6)

        self.lbl_stock = ttk.Label(version_frame, text="库存状态：未知")
        self.lbl_stock.pack(side=tk.LEFT, padx=12)

        self.var_headless = tk.BooleanVar(value=False)
        ttk.Checkbutton(version_frame, text="静默浏览器(Headless)", variable=self.var_headless).pack(side=tk.LEFT, padx=12)

        setting_frame = ttk.LabelFrame(self, text="执行设置")
        setting_frame.pack(fill=tk.X, padx=12, pady=6)

        self.var_max_workers = tk.StringVar(value="3")
        self.var_min_refresh = tk.StringVar(value="15")
        self.var_max_refresh = tk.StringVar(value="60")
        self.var_max_refresh_attempts = tk.StringVar(value="120")
        self.var_max_monitor_minutes = tk.StringVar(value="120")
        self.var_retry_count = tk.StringVar(value="0")

        ttk.Label(setting_frame, text="并发数").pack(side=tk.LEFT, padx=(6, 4))
        ttk.Entry(setting_frame, textvariable=self.var_max_workers, width=6).pack(side=tk.LEFT)
        ttk.Label(setting_frame, text="最小刷新(s)").pack(side=tk.LEFT, padx=(10, 4))
        ttk.Entry(setting_frame, textvariable=self.var_min_refresh, width=6).pack(side=tk.LEFT)
        ttk.Label(setting_frame, text="最大刷新(s)").pack(side=tk.LEFT, padx=(10, 4))
        ttk.Entry(setting_frame, textvariable=self.var_max_refresh, width=6).pack(side=tk.LEFT)
        ttk.Label(setting_frame, text="最大刷新次数").pack(side=tk.LEFT, padx=(10, 4))
        ttk.Entry(setting_frame, textvariable=self.var_max_refresh_attempts, width=6).pack(side=tk.LEFT)
        ttk.Label(setting_frame, text="最大监控(分)").pack(side=tk.LEFT, padx=(10, 4))
        ttk.Entry(setting_frame, textvariable=self.var_max_monitor_minutes, width=6).pack(side=tk.LEFT)
        ttk.Label(setting_frame, text="重试次数").pack(side=tk.LEFT, padx=(10, 4))
        ttk.Entry(setting_frame, textvariable=self.var_retry_count, width=6).pack(side=tk.LEFT)

        control_frame = ttk.Frame(self)
        control_frame.pack(fill=tk.X, padx=12, pady=8)

        self.btn_start_normal = ttk.Button(control_frame, text="正常加购", command=lambda: self._start(monitor_mode=False))
        self.btn_start_normal.pack(side=tk.LEFT, padx=8)
        self.btn_start_monitor = ttk.Button(control_frame, text="缺货监控", command=lambda: self._start(monitor_mode=True))
        self.btn_start_monitor.pack(side=tk.LEFT, padx=8)
        self.btn_stop = ttk.Button(control_frame, text="停止任务", command=self._stop, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=8)

        self.lbl_summary = ttk.Label(control_frame, text="总数:0 成功:0 失败:0 取消:0")
        self.lbl_summary.pack(side=tk.LEFT, padx=18)

        ttk.Label(self, text="日志：").pack(anchor="w", padx=12)
        self.txt = tk.Text(self, height=28)
        self.txt.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)
        self.txt.configure(state=tk.DISABLED)

    def _pick_docx(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Word 文档", "*.docx")])
        if not path:
            return
        self.var_docx.set(path)
        self._refresh_account_count()

    def _refresh_account_count(self) -> None:
        count = len(read_accounts_from_docx(self.var_docx.get().strip()))
        self.lbl_count.configure(text=f"已解析账号：{count} 个")

    def _append_log(self, line: str) -> None:
        self.txt.configure(state=tk.NORMAL)
        self.txt.insert(tk.END, line + "\n")
        self.txt.see(tk.END)
        self.txt.configure(state=tk.DISABLED)

    def _log(self, message: str) -> None:
        self.log_queue.put(message)

    def _drain_queues(self) -> None:
        while True:
            try:
                line = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self._append_log(line)
            if self.run_logger:
                self.run_logger.write(line)

        while True:
            try:
                event, payload = self.event_queue.get_nowait()
            except queue.Empty:
                break
            if event == "result":
                self._handle_result(payload)  # type: ignore[arg-type]
            elif event == "done":
                self._handle_done()

        self.after(100, self._drain_queues)

    def _preload(self) -> None:
        url = self.var_url.get().strip()
        if not url:
            messagebox.showerror("错误", "请输入 URL")
            return

        try:
            result = preload_product(url)
        except Exception as exc:
            messagebox.showerror("预加载失败", str(exc))
            return

        self.cmb_version["values"] = result.versions
        if result.versions:
            self.cmb_version.current(0)
        self.lbl_stock.configure(text="库存状态：有货" if result.in_stock else "库存状态：缺货")
        self._log("预加载完成")

    def _build_config(self, monitor_mode: bool) -> JobConfig:
        return JobConfig(
            product_url=self.var_url.get().strip(),
            version=self.cmb_version.get().strip() or "默认",
            monitor_mode=monitor_mode,
            headless=self.var_headless.get(),
            max_workers=int(self.var_max_workers.get().strip()),
            min_refresh_sec=int(self.var_min_refresh.get().strip()),
            max_refresh_sec=int(self.var_max_refresh.get().strip()),
            max_refresh_attempts=int(self.var_max_refresh_attempts.get().strip()),
            max_monitor_minutes=int(self.var_max_monitor_minutes.get().strip()),
            retry_count=int(self.var_retry_count.get().strip()),
        )

    def _collect_settings(self) -> AppSettings:
        return AppSettings(
            docx_path=self.var_docx.get().strip(),
            product_url=self.var_url.get().strip(),
            version=self.cmb_version.get().strip() or "默认",
            headless=self.var_headless.get(),
            max_workers=int(self.var_max_workers.get().strip() or "3"),
            min_refresh_sec=int(self.var_min_refresh.get().strip() or "15"),
            max_refresh_sec=int(self.var_max_refresh.get().strip() or "60"),
            max_refresh_attempts=int(self.var_max_refresh_attempts.get().strip() or "120"),
            max_monitor_minutes=int(self.var_max_monitor_minutes.get().strip() or "120"),
            retry_count=int(self.var_retry_count.get().strip() or "0"),
        )

    def _save_settings(self) -> None:
        try:
            settings = self._collect_settings()
            settings_path = save_settings(settings)
            self._log(f"已保存基本信息：{settings_path}")
            messagebox.showinfo("成功", f"已保存到：{settings_path}")
        except Exception as exc:
            messagebox.showerror("保存失败", str(exc))

    def _load_settings_into_ui(self) -> None:
        settings = load_settings()
        if settings.docx_path:
            self.var_docx.set(settings.docx_path)
        if settings.product_url:
            self.var_url.set(settings.product_url)

        self.var_headless.set(settings.headless)
        self.var_max_workers.set(str(settings.max_workers))
        self.var_min_refresh.set(str(settings.min_refresh_sec))
        self.var_max_refresh.set(str(settings.max_refresh_sec))
        self.var_max_refresh_attempts.set(str(settings.max_refresh_attempts))
        self.var_max_monitor_minutes.set(str(settings.max_monitor_minutes))
        self.var_retry_count.set(str(settings.retry_count))

        if settings.version and settings.version != "默认":
            self.cmb_version["values"] = [settings.version]
            self.cmb_version.current(0)

    def _start(self, monitor_mode: bool) -> None:
        if self.service.is_running:
            messagebox.showwarning("提示", "任务已在运行中")
            return

        accounts = read_accounts_from_docx(self.var_docx.get().strip())
        if not accounts:
            messagebox.showerror("错误", "账号文件无有效账号")
            return

        try:
            config = self._build_config(monitor_mode)
            config.validate()
            save_settings(self._collect_settings())
        except Exception as exc:
            messagebox.showerror("参数错误", str(exc))
            return

        self.success_count = 0
        self.failed_count = 0
        self.cancelled_count = 0
        self.total_count = len(accounts)
        self._update_summary()

        self.run_logger = RunLogger(Path.cwd() / "logs")
        self._set_running_ui(True)
        self._log(f"开始任务：账号数={len(accounts)}，模式={'缺货监控' if monitor_mode else '正常加购'}")
        self._log(f"日志文件：{self.run_logger.file_path}")

        started = self.service.start(
            accounts=accounts,
            config=config,
            log_fn=self._log,
            result_fn=lambda r: self.event_queue.put(("result", r)),
            done_fn=lambda: self.event_queue.put(("done", None)),
        )
        if not started:
            self._set_running_ui(False)
            messagebox.showwarning("提示", "任务已在运行中")

    def _stop(self) -> None:
        if not self.service.is_running:
            return
        self.service.stop()
        self._log("已请求停止任务，正在等待线程退出")

    def _handle_result(self, result: WorkerResult) -> None:
        if result.status == "success":
            self.success_count += 1
        elif result.status == "cancelled":
            self.cancelled_count += 1
        else:
            self.failed_count += 1

        suffix = f" attempts={result.attempts} duration={result.duration_sec:.1f}s"
        if result.error_code:
            suffix += f" code={result.error_code}"
        self._log(f"[{result.username}] {result.status}: {result.message}{suffix}")
        self._update_summary()

    def _handle_done(self) -> None:
        self._set_running_ui(False)
        self._log("任务已结束")

    def _update_summary(self) -> None:
        self.lbl_summary.configure(
            text=f"总数:{self.total_count} 成功:{self.success_count} 失败:{self.failed_count} 取消:{self.cancelled_count}"
        )

    def _set_running_ui(self, running: bool) -> None:
        self.btn_start_normal.configure(state=tk.DISABLED if running else tk.NORMAL)
        self.btn_start_monitor.configure(state=tk.DISABLED if running else tk.NORMAL)
        self.btn_stop.configure(state=tk.NORMAL if running else tk.DISABLED)
