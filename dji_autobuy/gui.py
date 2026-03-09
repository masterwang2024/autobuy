from __future__ import annotations

import queue
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from .models import Account, JobConfig, WorkerResult
from .run_logger import RunLogger
from .service import AutobuyService, TaskRunSpec
from .settings_store import AppSettings, StoredAccount, StoredTask, load_settings, save_settings


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("DJI Autobuy Control Center")
        self.geometry("1180x820")
        self.minsize(1100, 760)

        self.service = AutobuyService()
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.event_queue: queue.Queue[tuple[str, object]] = queue.Queue()

        self.accounts: list[StoredAccount] = []
        self.tasks: list[StoredTask] = []

        self.success_count = 0
        self.failed_count = 0
        self.cancelled_count = 0
        self.total_count = 0
        self.completed_count = 0
        self.run_logger: RunLogger | None = None

        self._build_style()
        self._build_ui()
        self._load_settings_into_ui()
        self.after(100, self._drain_queues)

    def _build_style(self) -> None:
        self.colors = {
            "bg": "#f5f7fb",
            "card": "#ffffff",
            "text": "#1f2937",
            "muted": "#667085",
        }
        self.configure(bg=self.colors["bg"])

        style = ttk.Style(self)
        try:
            style.theme_use("aqua")
        except tk.TclError:
            style.theme_use("clam")
        style.configure("App.TFrame", background=self.colors["bg"])
        style.configure("Card.TLabelframe", background=self.colors["card"], borderwidth=1)
        style.configure("Card.TLabelframe.Label", background=self.colors["card"], foreground=self.colors["text"], font=("SF Pro Text", 12, "bold"))
        style.configure("Text.TLabel", background=self.colors["card"], foreground=self.colors["text"], font=("SF Pro Text", 11))
        style.configure("Sub.TLabel", background=self.colors["bg"], foreground=self.colors["muted"], font=("SF Pro Text", 11))

    def _build_ui(self) -> None:
        shell = ttk.Frame(self, style="App.TFrame")
        shell.pack(fill=tk.BOTH, expand=True, padx=16, pady=14)

        ttk.Label(shell, text="DJI 自动加购控制台", style="Text.TLabel", font=("SF Pro Display", 22, "bold")).pack(anchor="w")
        ttk.Label(shell, text="账号和任务全部在 APP 内配置，不依赖本地账号文档", style="Sub.TLabel").pack(anchor="w", pady=(0, 10))

        body = ttk.Frame(shell, style="App.TFrame")
        body.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(body, style="App.TFrame", width=640)
        left.pack(side=tk.LEFT, fill=tk.BOTH)
        left.pack_propagate(False)

        right = ttk.Frame(body, style="App.TFrame")
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0))

        self._build_left(left)
        self._build_right(right)

    def _build_left(self, parent: ttk.Frame) -> None:
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True)

        tab_accounts = ttk.Frame(notebook)
        tab_tasks = ttk.Frame(notebook)
        tab_params = ttk.Frame(notebook)

        notebook.add(tab_accounts, text="账号配置")
        notebook.add(tab_tasks, text="任务配置")
        notebook.add(tab_params, text="执行参数")

        self._build_accounts_tab(tab_accounts)
        self._build_tasks_tab(tab_tasks)
        self._build_params_tab(tab_params)

    def _build_accounts_tab(self, parent: ttk.Frame) -> None:
        card = ttk.LabelFrame(parent, text="账号列表", style="Card.TLabelframe")
        card.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.account_tree = ttk.Treeview(card, columns=("username", "enabled"), show="headings", height=12)
        self.account_tree.heading("username", text="账号")
        self.account_tree.heading("enabled", text="启用")
        self.account_tree.column("username", width=260)
        self.account_tree.column("enabled", width=80, anchor="center")
        self.account_tree.pack(fill=tk.X, padx=10, pady=(10, 6))
        self.account_tree.bind("<<TreeviewSelect>>", lambda _: self._load_selected_account())

        form = ttk.Frame(card)
        form.pack(fill=tk.X, padx=10, pady=6)

        self.var_acc_username = tk.StringVar()
        self.var_acc_password = tk.StringVar()
        self.var_acc_enabled = tk.BooleanVar(value=True)

        ttk.Label(form, text="账号", style="Text.TLabel").grid(row=0, column=0, sticky="w", padx=4)
        ttk.Entry(form, textvariable=self.var_acc_username, width=28).grid(row=1, column=0, sticky="w", padx=4, pady=(2, 8))
        ttk.Label(form, text="密码", style="Text.TLabel").grid(row=0, column=1, sticky="w", padx=4)
        ttk.Entry(form, textvariable=self.var_acc_password, show="*", width=28).grid(row=1, column=1, sticky="w", padx=4, pady=(2, 8))
        ttk.Checkbutton(form, text="启用该账号", variable=self.var_acc_enabled).grid(row=1, column=2, sticky="w", padx=8)

        buttons = ttk.Frame(card)
        buttons.pack(fill=tk.X, padx=10, pady=(2, 10))
        ttk.Button(buttons, text="新增账号", command=self._add_account).pack(side=tk.LEFT)
        ttk.Button(buttons, text="更新账号", command=self._update_account).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(buttons, text="删除账号", command=self._delete_account).pack(side=tk.LEFT, padx=(8, 0))

    def _build_tasks_tab(self, parent: ttk.Frame) -> None:
        card = ttk.LabelFrame(parent, text="任务列表", style="Card.TLabelframe")
        card.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.task_tree = ttk.Treeview(card, columns=("name", "url", "mode", "accounts", "enabled"), show="headings", height=10)
        self.task_tree.heading("name", text="任务名")
        self.task_tree.heading("url", text="购买 URL")
        self.task_tree.heading("mode", text="模式")
        self.task_tree.heading("accounts", text="账号数")
        self.task_tree.heading("enabled", text="启用")
        self.task_tree.column("name", width=150)
        self.task_tree.column("url", width=260)
        self.task_tree.column("mode", width=80, anchor="center")
        self.task_tree.column("accounts", width=70, anchor="center")
        self.task_tree.column("enabled", width=70, anchor="center")
        self.task_tree.pack(fill=tk.X, padx=10, pady=(10, 6))
        self.task_tree.bind("<<TreeviewSelect>>", lambda _: self._load_selected_task())

        form = ttk.Frame(card)
        form.pack(fill=tk.X, padx=10, pady=6)

        self.var_task_name = tk.StringVar()
        self.var_task_url = tk.StringVar()
        self.var_task_version = tk.StringVar(value="默认")
        self.var_task_monitor = tk.BooleanVar(value=False)
        self.var_task_enabled = tk.BooleanVar(value=True)

        ttk.Label(form, text="任务名", style="Text.TLabel").grid(row=0, column=0, sticky="w", padx=4)
        ttk.Entry(form, textvariable=self.var_task_name, width=20).grid(row=1, column=0, sticky="w", padx=4, pady=(2, 8))
        ttk.Label(form, text="购买 URL", style="Text.TLabel").grid(row=0, column=1, sticky="w", padx=4)
        ttk.Entry(form, textvariable=self.var_task_url, width=44).grid(row=1, column=1, sticky="w", padx=4, pady=(2, 8))
        ttk.Label(form, text="版本", style="Text.TLabel").grid(row=0, column=2, sticky="w", padx=4)
        ttk.Entry(form, textvariable=self.var_task_version, width=12).grid(row=1, column=2, sticky="w", padx=4, pady=(2, 8))

        opts = ttk.Frame(card)
        opts.pack(fill=tk.X, padx=10)
        ttk.Checkbutton(opts, text="缺货监控模式", variable=self.var_task_monitor).pack(side=tk.LEFT)
        ttk.Checkbutton(opts, text="启用该任务", variable=self.var_task_enabled).pack(side=tk.LEFT, padx=(10, 0))

        assign = ttk.LabelFrame(card, text="该任务使用的账号（多选）", style="Card.TLabelframe")
        assign.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        self.task_account_list = tk.Listbox(assign, selectmode=tk.MULTIPLE, height=6)
        self.task_account_list.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        buttons = ttk.Frame(card)
        buttons.pack(fill=tk.X, padx=10, pady=(2, 10))
        ttk.Button(buttons, text="新增任务", command=self._add_task).pack(side=tk.LEFT)
        ttk.Button(buttons, text="更新任务", command=self._update_task).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(buttons, text="删除任务", command=self._delete_task).pack(side=tk.LEFT, padx=(8, 0))

    def _build_params_tab(self, parent: ttk.Frame) -> None:
        card = ttk.LabelFrame(parent, text="全局执行参数", style="Card.TLabelframe")
        card.pack(fill=tk.X, padx=8, pady=8)

        self.var_headless = tk.BooleanVar(value=False)
        self.var_max_workers = tk.StringVar(value="3")
        self.var_min_refresh = tk.StringVar(value="15")
        self.var_max_refresh = tk.StringVar(value="60")
        self.var_max_refresh_attempts = tk.StringVar(value="120")
        self.var_max_monitor_minutes = tk.StringVar(value="120")
        self.var_retry_count = tk.StringVar(value="0")

        grid = ttk.Frame(card)
        grid.pack(fill=tk.X, padx=10, pady=10)

        items = [
            ("并发数", self.var_max_workers),
            ("最小刷新(s)", self.var_min_refresh),
            ("最大刷新(s)", self.var_max_refresh),
            ("最大刷新次数", self.var_max_refresh_attempts),
            ("最大监控(分)", self.var_max_monitor_minutes),
            ("重试次数", self.var_retry_count),
        ]
        for i, (label, var) in enumerate(items):
            ttk.Label(grid, text=label, style="Text.TLabel").grid(row=i // 3 * 2, column=i % 3, sticky="w", padx=6, pady=(0, 4))
            ttk.Entry(grid, textvariable=var, width=16).grid(row=i // 3 * 2 + 1, column=i % 3, sticky="w", padx=6, pady=(0, 8))

        ttk.Checkbutton(grid, text="静默浏览器（Headless）", variable=self.var_headless).grid(row=4, column=0, sticky="w", padx=6, pady=(4, 0))

        btns = ttk.Frame(card)
        btns.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Button(btns, text="保存配置", command=self._save_settings).pack(side=tk.LEFT)

    def _build_right(self, parent: ttk.Frame) -> None:
        status = ttk.LabelFrame(parent, text="执行状态", style="Card.TLabelframe")
        status.pack(fill=tk.X)

        self.lbl_phase = ttk.Label(status, text="待命中", style="Sub.TLabel")
        self.lbl_phase.pack(anchor="w", padx=10, pady=(10, 6))

        self.progress = ttk.Progressbar(status, orient="horizontal", mode="determinate", maximum=100)
        self.progress.pack(fill=tk.X, padx=10)

        self.lbl_summary = ttk.Label(status, text="总数:0  完成:0  成功:0  失败:0  取消:0", style="Text.TLabel")
        self.lbl_summary.pack(anchor="w", padx=10, pady=(8, 10))

        controls = ttk.LabelFrame(parent, text="任务执行", style="Card.TLabelframe")
        controls.pack(fill=tk.X, pady=(10, 0))
        row = ttk.Frame(controls)
        row.pack(fill=tk.X, padx=10, pady=10)

        self.btn_run_selected = ttk.Button(row, text="执行选中任务", command=self._run_selected_tasks)
        self.btn_run_selected.pack(side=tk.LEFT)
        self.btn_run_all = ttk.Button(row, text="执行全部启用任务", command=self._run_all_tasks)
        self.btn_run_all.pack(side=tk.LEFT, padx=(8, 0))
        self.btn_stop = ttk.Button(row, text="停止任务", command=self._stop, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=(8, 0))

        logs = ttk.LabelFrame(parent, text="活动日志", style="Card.TLabelframe")
        logs.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        self.txt = tk.Text(logs, height=22, bg="#f8fafc", fg="#1f2937", font=("Menlo", 11), relief=tk.SOLID, borderwidth=1)
        self.txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.txt.configure(state=tk.DISABLED)

    def _load_selected_account(self) -> None:
        sel = self.account_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        acc = self.accounts[idx]
        self.var_acc_username.set(acc.username)
        self.var_acc_password.set(acc.password)
        self.var_acc_enabled.set(acc.enabled)

    def _add_account(self) -> None:
        username = self.var_acc_username.get().strip()
        password = self.var_acc_password.get().strip()
        if not username or not password:
            messagebox.showerror("错误", "账号和密码不能为空")
            return
        if any(a.username == username for a in self.accounts):
            messagebox.showerror("错误", "账号已存在")
            return
        self.accounts.append(StoredAccount(username=username, password=password, enabled=self.var_acc_enabled.get()))
        self._refresh_account_views()
        self._persist_settings()

    def _update_account(self) -> None:
        sel = self.account_tree.selection()
        if not sel:
            messagebox.showerror("错误", "请先选择账号")
            return
        idx = int(sel[0])
        username = self.var_acc_username.get().strip()
        password = self.var_acc_password.get().strip()
        if not username or not password:
            messagebox.showerror("错误", "账号和密码不能为空")
            return
        self.accounts[idx] = StoredAccount(username=username, password=password, enabled=self.var_acc_enabled.get())
        self._refresh_account_views()
        self._persist_settings()

    def _delete_account(self) -> None:
        sel = self.account_tree.selection()
        if not sel:
            messagebox.showerror("错误", "请先选择账号")
            return
        idx = int(sel[0])
        username = self.accounts[idx].username
        del self.accounts[idx]
        for t in self.tasks:
            if t.account_usernames:
                t.account_usernames = [u for u in t.account_usernames if u != username]
        self._refresh_account_views()
        self._refresh_task_views()
        self._persist_settings()

    def _load_selected_task(self) -> None:
        sel = self.task_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        task = self.tasks[idx]
        self.var_task_name.set(task.name)
        self.var_task_url.set(task.url)
        self.var_task_version.set(task.version)
        self.var_task_monitor.set(task.monitor_mode)
        self.var_task_enabled.set(task.enabled)

        self.task_account_list.selection_clear(0, tk.END)
        selected = set(task.account_usernames or [])
        usernames = [a.username for a in self.accounts]
        for i, username in enumerate(usernames):
            if username in selected:
                self.task_account_list.selection_set(i)

    def _collect_selected_task_accounts(self) -> list[str]:
        usernames = [a.username for a in self.accounts]
        return [usernames[i] for i in self.task_account_list.curselection()]

    def _add_task(self) -> None:
        name = self.var_task_name.get().strip()
        url = self.var_task_url.get().strip()
        if not name or not url:
            messagebox.showerror("错误", "任务名和 URL 不能为空")
            return
        if any(t.name == name for t in self.tasks):
            messagebox.showerror("错误", "任务名已存在")
            return
        self.tasks.append(
            StoredTask(
                name=name,
                url=url,
                version=self.var_task_version.get().strip() or "默认",
                monitor_mode=self.var_task_monitor.get(),
                enabled=self.var_task_enabled.get(),
                account_usernames=self._collect_selected_task_accounts(),
            )
        )
        self._refresh_task_views()
        self._persist_settings()

    def _update_task(self) -> None:
        sel = self.task_tree.selection()
        if not sel:
            messagebox.showerror("错误", "请先选择任务")
            return
        idx = int(sel[0])
        name = self.var_task_name.get().strip()
        url = self.var_task_url.get().strip()
        if not name or not url:
            messagebox.showerror("错误", "任务名和 URL 不能为空")
            return
        self.tasks[idx] = StoredTask(
            name=name,
            url=url,
            version=self.var_task_version.get().strip() or "默认",
            monitor_mode=self.var_task_monitor.get(),
            enabled=self.var_task_enabled.get(),
            account_usernames=self._collect_selected_task_accounts(),
        )
        self._refresh_task_views()
        self._persist_settings()

    def _delete_task(self) -> None:
        sel = self.task_tree.selection()
        if not sel:
            messagebox.showerror("错误", "请先选择任务")
            return
        idx = int(sel[0])
        del self.tasks[idx]
        self._refresh_task_views()
        self._persist_settings()

    def _refresh_account_views(self) -> None:
        for row in self.account_tree.get_children():
            self.account_tree.delete(row)
        for i, acc in enumerate(self.accounts):
            self.account_tree.insert("", tk.END, iid=str(i), values=(acc.username, "是" if acc.enabled else "否"))

        self.task_account_list.delete(0, tk.END)
        for acc in self.accounts:
            self.task_account_list.insert(tk.END, acc.username)

    def _refresh_task_views(self) -> None:
        for row in self.task_tree.get_children():
            self.task_tree.delete(row)
        for i, task in enumerate(self.tasks):
            mode = "监控" if task.monitor_mode else "正常"
            account_count = len(task.account_usernames or [])
            self.task_tree.insert("", tk.END, iid=str(i), values=(task.name, task.url, mode, account_count, "是" if task.enabled else "否"))

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
            elif event == "task":
                self._handle_task_event(payload)  # type: ignore[arg-type]
            elif event == "done":
                self._handle_done()

        self.after(100, self._drain_queues)

    def _build_global_config(self, task: StoredTask) -> JobConfig:
        return JobConfig(
            product_url=task.url,
            version=task.version or "默认",
            monitor_mode=task.monitor_mode,
            headless=self.var_headless.get(),
            max_workers=int(self.var_max_workers.get().strip()),
            min_refresh_sec=int(self.var_min_refresh.get().strip()),
            max_refresh_sec=int(self.var_max_refresh.get().strip()),
            max_refresh_attempts=int(self.var_max_refresh_attempts.get().strip()),
            max_monitor_minutes=int(self.var_max_monitor_minutes.get().strip()),
            retry_count=int(self.var_retry_count.get().strip()),
        )

    def _build_task_specs(self, selected_task_indices: list[int]) -> list[TaskRunSpec]:
        account_map = {a.username: a for a in self.accounts if a.enabled}
        specs: list[TaskRunSpec] = []
        for idx in selected_task_indices:
            task = self.tasks[idx]
            if not task.enabled:
                continue
            usernames = task.account_usernames or list(account_map.keys())
            selected_accounts: list[Account] = []
            for username in usernames:
                account = account_map.get(username)
                if account:
                    selected_accounts.append(Account(username=account.username, password=account.password))
            if not selected_accounts:
                self._log(f"任务 {task.name} 跳过：无可用账号")
                continue
            config = self._build_global_config(task)
            config.validate()
            specs.append(TaskRunSpec(task_name=task.name, accounts=selected_accounts, config=config))
        return specs

    def _run_selected_tasks(self) -> None:
        selected = self.task_tree.selection()
        if not selected:
            messagebox.showerror("错误", "请先在任务列表里选中至少一个任务")
            return
        self._run_with_indices([int(i) for i in selected])

    def _run_all_tasks(self) -> None:
        enabled_indices = [i for i, t in enumerate(self.tasks) if t.enabled]
        if not enabled_indices:
            messagebox.showerror("错误", "没有启用任务")
            return
        self._run_with_indices(enabled_indices)

    def _run_with_indices(self, indices: list[int]) -> None:
        if self.service.is_running:
            messagebox.showwarning("提示", "已有任务在运行")
            return
        if not self.accounts:
            messagebox.showerror("错误", "请先配置账号")
            return
        if not self.tasks:
            messagebox.showerror("错误", "请先配置任务")
            return

        try:
            task_specs = self._build_task_specs(indices)
            if not task_specs:
                messagebox.showerror("错误", "没有可执行任务（请检查任务启用和账号分配）")
                return
            self._persist_settings()
        except Exception as exc:
            messagebox.showerror("参数错误", str(exc))
            return

        self.success_count = 0
        self.failed_count = 0
        self.cancelled_count = 0
        self.completed_count = 0
        self.total_count = sum(len(spec.accounts) for spec in task_specs)
        self._update_summary()

        self.run_logger = RunLogger(Path.cwd() / "logs")
        self._set_running_ui(True)
        self.lbl_phase.configure(text="任务运行中")
        self._log(f"开始多任务执行：任务数={len(task_specs)}，总账号执行数={self.total_count}")

        started = self.service.start_tasks(
            task_specs=task_specs,
            log_fn=self._log,
            result_fn=lambda r: self.event_queue.put(("result", r)),
            task_event_fn=lambda e: self.event_queue.put(("task", e)),
            done_fn=lambda: self.event_queue.put(("done", None)),
        )
        if not started:
            self._set_running_ui(False)
            messagebox.showwarning("提示", "已有任务在运行")

    def _stop(self) -> None:
        if not self.service.is_running:
            return
        self.service.stop()
        self.lbl_phase.configure(text="已请求停止，等待任务退出")
        self._log("已请求停止任务")

    def _handle_result(self, result: WorkerResult) -> None:
        self.completed_count += 1
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

    def _handle_task_event(self, event: str) -> None:
        if event.startswith("start:"):
            self.lbl_phase.configure(text=f"运行中：{event.split(':', 1)[1]}")
            self._log(f"任务开始：{event.split(':', 1)[1]}")
        elif event.startswith("done:"):
            self._log(f"任务完成：{event.split(':', 1)[1]}")

    def _handle_done(self) -> None:
        self._set_running_ui(False)
        self.lbl_phase.configure(text="全部任务结束")
        self._log("全部任务结束")

    def _update_summary(self) -> None:
        progress_value = (self.completed_count / self.total_count * 100) if self.total_count else 0
        self.progress["value"] = progress_value
        self.lbl_summary.configure(
            text=(
                f"总数:{self.total_count}  完成:{self.completed_count}  "
                f"成功:{self.success_count}  失败:{self.failed_count}  取消:{self.cancelled_count}"
            )
        )

    def _set_running_ui(self, running: bool) -> None:
        self.btn_run_selected.configure(state=tk.DISABLED if running else tk.NORMAL)
        self.btn_run_all.configure(state=tk.DISABLED if running else tk.NORMAL)
        self.btn_stop.configure(state=tk.NORMAL if running else tk.DISABLED)

    def _collect_settings(self) -> AppSettings:
        return AppSettings(
            accounts=self.accounts,
            tasks=self.tasks,
            headless=self.var_headless.get(),
            max_workers=int(self.var_max_workers.get().strip() or "3"),
            min_refresh_sec=int(self.var_min_refresh.get().strip() or "15"),
            max_refresh_sec=int(self.var_max_refresh.get().strip() or "60"),
            max_refresh_attempts=int(self.var_max_refresh_attempts.get().strip() or "120"),
            max_monitor_minutes=int(self.var_max_monitor_minutes.get().strip() or "120"),
            retry_count=int(self.var_retry_count.get().strip() or "0"),
        )

    def _persist_settings(self) -> None:
        save_settings(self._collect_settings())

    def _save_settings(self) -> None:
        try:
            self._persist_settings()
            self._log("配置已保存")
            messagebox.showinfo("成功", "配置已保存")
        except Exception as exc:
            messagebox.showerror("保存失败", str(exc))

    def _load_settings_into_ui(self) -> None:
        settings = load_settings()
        self.accounts = settings.normalized_accounts()
        self.tasks = settings.normalized_tasks()

        self.var_headless.set(settings.headless)
        self.var_max_workers.set(str(settings.max_workers))
        self.var_min_refresh.set(str(settings.min_refresh_sec))
        self.var_max_refresh.set(str(settings.max_refresh_sec))
        self.var_max_refresh_attempts.set(str(settings.max_refresh_attempts))
        self.var_max_monitor_minutes.set(str(settings.max_monitor_minutes))
        self.var_retry_count.set(str(settings.retry_count))

        self._refresh_account_views()
        self._refresh_task_views()
