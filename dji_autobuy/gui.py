from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .accounts import read_accounts_from_docx
from .models import JobConfig
from .scraper import preload_product
from .worker import run_worker


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("DJI 多账号自动加购")
        self.geometry("980x760")

        self.log_queue: queue.Queue[str] = queue.Queue()
        self._build_ui()
        self._refresh_account_count()
        self.after(100, self._drain_logs)

    def _build_ui(self) -> None:
        account_frame = ttk.LabelFrame(self, text="账号文件")
        account_frame.pack(fill=tk.X, padx=12, pady=6)

        default_docx = Path(__file__).resolve().parent.parent / "账号信息.docx"
        self.var_docx = tk.StringVar(value=str(default_docx))
        ttk.Entry(account_frame, textvariable=self.var_docx, width=78).pack(side=tk.LEFT, padx=6)
        ttk.Button(account_frame, text="选择", command=self._pick_docx).pack(side=tk.LEFT)
        self.lbl_count = ttk.Label(account_frame, text="未读取")
        self.lbl_count.pack(side=tk.LEFT, padx=8)

        product_frame = ttk.LabelFrame(self, text="商品")
        product_frame.pack(fill=tk.X, padx=12, pady=6)

        self.var_url = tk.StringVar()
        ttk.Label(product_frame, text="URL:").pack(side=tk.LEFT)
        ttk.Entry(product_frame, textvariable=self.var_url, width=82).pack(side=tk.LEFT, padx=6)
        ttk.Button(product_frame, text="预加载", command=self._preload).pack(side=tk.LEFT)

        version_frame = ttk.LabelFrame(self, text="版本与库存")
        version_frame.pack(fill=tk.X, padx=12, pady=6)

        self.cmb_version = ttk.Combobox(version_frame, values=[], width=30, state="readonly")
        self.cmb_version.pack(side=tk.LEFT, padx=6)

        self.lbl_stock = ttk.Label(version_frame, text="库存状态：未知")
        self.lbl_stock.pack(side=tk.LEFT, padx=12)

        self.var_headless = tk.BooleanVar(value=False)
        ttk.Checkbutton(version_frame, text="静默浏览器(Headless)", variable=self.var_headless).pack(side=tk.LEFT, padx=12)

        setting_frame = ttk.LabelFrame(self, text="监控设置")
        setting_frame.pack(fill=tk.X, padx=12, pady=6)

        self.var_min_refresh = tk.StringVar(value="15")
        self.var_max_refresh = tk.StringVar(value="60")
        ttk.Label(setting_frame, text="最小刷新(s)").pack(side=tk.LEFT, padx=(6, 4))
        ttk.Entry(setting_frame, textvariable=self.var_min_refresh, width=8).pack(side=tk.LEFT)
        ttk.Label(setting_frame, text="最大刷新(s)").pack(side=tk.LEFT, padx=(12, 4))
        ttk.Entry(setting_frame, textvariable=self.var_max_refresh, width=8).pack(side=tk.LEFT)

        control_frame = ttk.Frame(self)
        control_frame.pack(fill=tk.X, padx=12, pady=8)

        ttk.Button(control_frame, text="正常加购", command=lambda: self._start(monitor_mode=False)).pack(side=tk.LEFT, padx=8)
        ttk.Button(control_frame, text="缺货监控", command=lambda: self._start(monitor_mode=True)).pack(side=tk.LEFT, padx=8)

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

    def _drain_logs(self) -> None:
        while True:
            try:
                line = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self._append_log(line)
        self.after(100, self._drain_logs)

    def _append_log(self, line: str) -> None:
        self.txt.configure(state=tk.NORMAL)
        self.txt.insert(tk.END, line + "\n")
        self.txt.see(tk.END)
        self.txt.configure(state=tk.DISABLED)

    def _log(self, message: str) -> None:
        self.log_queue.put(message)

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
            min_refresh_sec=int(self.var_min_refresh.get().strip()),
            max_refresh_sec=int(self.var_max_refresh.get().strip()),
        )

    def _start(self, monitor_mode: bool) -> None:
        accounts = read_accounts_from_docx(self.var_docx.get().strip())
        if not accounts:
            messagebox.showerror("错误", "账号文件无有效账号")
            return

        try:
            config = self._build_config(monitor_mode)
            config.validate()
        except Exception as exc:
            messagebox.showerror("参数错误", str(exc))
            return

        self._log(f"开始任务：账号数={len(accounts)}，模式={'缺货监控' if monitor_mode else '正常加购'}")
        for account in accounts:
            thread = threading.Thread(
                target=self._run_worker_safe,
                args=(account, config),
                daemon=True,
            )
            thread.start()

    def _run_worker_safe(self, account, config: JobConfig) -> None:
        try:
            run_worker(account, config, self._log)
        except Exception as exc:
            self._log(f"[{account.username}] 执行失败: {exc}")
