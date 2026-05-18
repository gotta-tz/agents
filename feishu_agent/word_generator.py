import subprocess
from pathlib import Path

class WordGenerator:
    """调用 5cun-docx-cli.py 生成 Word 文档"""

    def __init__(self, script_path, output_dir, python_path="python3", timeout=120):
        self.script_path = script_path
        self.output_dir = Path(output_dir)
        self.python_path = python_path
        self.timeout = timeout
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, image_dir, output_filename=None):
        """
        执行图片转 Word

        Returns:
            {"success": True, "output_path": "...", "photo_count": N}
            或
            {"success": False, "error": "错误信息"}
        """
        if not output_filename:
            import time
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_filename = f"5cun_{timestamp}.docx"

        output_path = self.output_dir / output_filename

        cmd = [
            self.python_path,
            self.script_path,
            image_dir,
            str(output_path)
        ]

        print(f"[执行] {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                shell=False
            )

            stdout = result.stdout or ""
            stderr = result.stderr or ""

            if "SUCCESS:" in stdout or result.returncode == 0:
                # 从输出中提取实际路径
                actual_path = stdout.split("SUCCESS:")[-1].strip().split("\n")[0] if "SUCCESS:" in stdout else str(output_path)
                return {
                    "success": True,
                    "output_path": actual_path,
                    "photo_count": None
                }
            else:
                return {
                    "success": False,
                    "error": stderr or stdout or "执行失败"
                }

        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"执行超时（{self.timeout}秒）"}
        except FileNotFoundError:
            return {"success": False, "error": f"找不到脚本: {self.script_path}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
