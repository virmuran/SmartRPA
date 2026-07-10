"""Task Manager — scan, list, rename, delete automation tasks.

Scans both built-in examples and user data directories.
Compatible with existing task.json format (reads _meta.name as display name).
"""
import os
import json
import datetime
import shutil

from smartrpa.ui.theme import resource_path, data_dir


class TaskManager:
    """Manages the lifecycle of automation tasks."""

    def __init__(self):
        """Initialize the task manager with an empty task map."""
        self._task_map = {}  # display_name → file_path

    # ═══════════════════════════════════════════════
    #  Scanning
    # ═══════════════════════════════════════════════

    def scan_tasks(self) -> list:
        """Scan built-in examples + user data, return list of task display names.

        Returns:
            List of task display names sorted alphabetically.
        """
        self._task_map.clear()

        # Scan built-in examples & copy to user data on first run
        ex = resource_path("examples")
        if os.path.isdir(ex):
            for d in sorted(os.listdir(ex)):
                src_fp = os.path.join(ex, d, "task.json")
                if not os.path.exists(src_fp):
                    continue
                # Read display name from _meta.name, fallback to folder name
                display = d
                try:
                    with open(src_fp, encoding="utf-8") as f:
                        data = json.load(f)
                        meta = data.get("_meta", {})
                        if isinstance(meta, dict) and meta.get("name"):
                            display = meta["name"]
                except (json.JSONDecodeError, IOError):
                    pass
                # Ensure a copy exists in user data directory
                user_task_dir = data_dir(f"tasks/{d}")
                user_fp = os.path.join(user_task_dir, "task.json")
                if not os.path.exists(user_fp):
                    os.makedirs(user_task_dir, exist_ok=True)
                    shutil.copy2(src_fp, user_fp)
                # Always sync templates
                src_tpl = os.path.join(ex, d, "templates")
                if os.path.isdir(src_tpl):
                    dst_tpl = os.path.join(user_task_dir, "templates")
                    os.makedirs(dst_tpl, exist_ok=True)
                    for fname in os.listdir(src_tpl):
                        s = os.path.join(src_tpl, fname)
                        d_path = os.path.join(dst_tpl, fname)
                        if os.path.isfile(s) and (
                            not os.path.exists(d_path)
                            or os.path.getmtime(s) > os.path.getmtime(d_path)
                        ):
                            shutil.copy2(s, d_path)
                # Register the user data copy as the active path
                self._task_map[display] = user_fp

        # Scan user data directory (timestamp folders, read _meta.name)
        user_dir = data_dir("tasks")
        if os.path.isdir(user_dir):
            for folder in sorted(os.listdir(user_dir)):
                # Skip folders that match built-in example names
                if os.path.isdir(ex) and os.path.isdir(os.path.join(ex, folder)):
                    continue
                fp = os.path.join(user_dir, folder, "task.json")
                if not os.path.exists(fp):
                    continue
                display = folder
                try:
                    with open(fp, encoding="utf-8") as f:
                        data = json.load(f)
                        meta = data.get("_meta", {})
                        if isinstance(meta, dict) and meta.get("name"):
                            display = meta["name"]
                except (json.JSONDecodeError, IOError):
                    pass
                # Deduplicate: append suffix if display name already taken
                key = display
                suffix = 1
                while key in self._task_map:
                    suffix += 1
                    key = f"{display} ({suffix})"
                self._task_map[key] = fp

        # Scan for Behavior Tree task files (*.bt.json)
        for scan_dir in (
            [ex] if os.path.isdir(ex) else []
        ) + [data_dir("tasks")]:
            if not os.path.isdir(scan_dir):
                continue
            for d in sorted(os.listdir(scan_dir)):
                bt_file = os.path.join(scan_dir, d)
                if os.path.isdir(bt_file):
                    bt_file = os.path.join(bt_file, "task.bt.json")
                elif not d.endswith(".bt.json"):
                    continue
                if not os.path.exists(bt_file):
                    continue
                try:
                    with open(bt_file, encoding="utf-8") as f:
                        bt_data = json.load(f)
                    bt_meta = bt_data.get("_meta", {})
                    bt_display = (
                        bt_meta.get("name", os.path.splitext(os.path.basename(d))[0])
                        if isinstance(bt_meta, dict)
                        else d
                    )
                except (json.JSONDecodeError, IOError):
                    continue
                bt_key = f"{bt_display} [BT]"
                if bt_key not in self._task_map:
                    self._task_map[bt_key] = bt_file

        return sorted(self._task_map.keys())

    # ═══════════════════════════════════════════════
    #  Accessors
    # ═══════════════════════════════════════════════

    def get_task_path(self, name: str) -> str:
        """Get the file path for a task by its display name.

        Args:
            name: The display name of the task.

        Returns:
            Absolute path to task.json or task.bt.json, or None if not found.
        """
        return self._task_map.get(name)

    def get_task_templates_dir(self, name: str) -> str:
        """Get the templates directory for a task.

        Args:
            name: The display name of the task.

        Returns:
            Absolute path to the templates directory, or None if not found.
        """
        path = self._task_map.get(name)
        if not path:
            return None
        tpl = os.path.join(os.path.dirname(path), "templates")
        if os.path.isdir(tpl):
            return tpl
        return None

    def get_all_tasks(self) -> dict:
        """Get the full task map.

        Returns:
            Dict mapping display_name → file_path.
        """
        return dict(self._task_map)

    # ═══════════════════════════════════════════════
    #  Mutators
    # ═══════════════════════════════════════════════

    def rename_task(self, name: str, new_name: str) -> bool:
        """Rename a user task by updating _meta.name in its task.json.

        Args:
            name: Current display name.
            new_name: New display name.

        Returns:
            True on success, False on failure (built-in task, not found, etc.).
        """
        path = self._task_map.get(name)
        if not path:
            return False
        # Built-in tasks cannot be renamed
        if path.startswith(resource_path("examples")):
            return False
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if "_meta" not in data or not isinstance(data["_meta"], dict):
                data["_meta"] = {}
            data["_meta"]["name"] = new_name
            data["_meta"]["modified"] = datetime.datetime.now().isoformat()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            # Update in-memory map
            del self._task_map[name]
            self._task_map[new_name] = path
            return True
        except (IOError, json.JSONDecodeError):
            return False

    def delete_task(self, name: str) -> bool:
        """Delete a user task folder entirely.

        Args:
            name: Display name of the task to delete.

        Returns:
            True on success, False on failure.
        """
        path = self._task_map.get(name)
        if not path:
            return False
        # Built-in tasks cannot be deleted
        if path.startswith(resource_path("examples")):
            return False
        task_dir = os.path.dirname(path)
        try:
            shutil.rmtree(task_dir)
            del self._task_map[name]
            return True
        except OSError:
            return False

    def is_builtin(self, name: str) -> bool:
        """Check if a task is a built-in (shipped) example.

        Args:
            name: Display name of the task.

        Returns:
            True if the task is a built-in example.
        """
        path = self._task_map.get(name)
        if not path:
            return False
        return path.startswith(resource_path("examples"))
