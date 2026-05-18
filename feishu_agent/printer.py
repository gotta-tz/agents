import subprocess
import re
import os
import tempfile
import zipfile
from pathlib import Path
from reportlab.pdfgen import canvas

class Printer:
    """Mac 打印机管理"""

    def __init__(self, printer_name=None):
        """
        Args:
            printer_name: 打印机名称，不指定则使用默认打印机
        """
        self.printer_name = printer_name

    def list_printers(self):
        """列出所有可用打印机"""
        try:
            result = subprocess.run(
                ["lpstat", "-a"],
                capture_output=True,
                text=True,
                timeout=10
            )
            printers = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    printer = line.split()[0]
                    printers.append(printer)
            return printers
        except Exception as e:
            return {"error": str(e)}

    def get_default_printer(self):
        """获取默认打印机"""
        try:
            result = subprocess.run(
                ["lpstat", "-d"],
                capture_output=True,
                text=True,
                timeout=10
            )
            match = re.search(r"no default destination|default destination: (.+)", result.stdout)
            if match:
                if "no default" in result.stdout:
                    return None
                return match.group(1)
            return None
        except Exception as e:
            return None

    def docx_to_pdf(self, docx_path):
        """
        将 docx 文件转换为 PDF
        使用 LibreOffice 转换，保持 Word 原有的排版
        """
        pdf_path = tempfile.mktemp(suffix='.pdf')

        try:
            # 使用 LibreOffice 转换 docx 为 PDF（使用完整路径）
            result = subprocess.run(
                [
                    "/opt/homebrew/bin/soffice",
                    "--headless",
                    "--convert-to", "pdf",
                    "--outdir", os.path.dirname(pdf_path),
                    docx_path
                ],
                capture_output=True,
                text=True,
                timeout=60
            )

            # LibreOffice 输出文件名可能与原文件相同
            expected_pdf = os.path.join(
                os.path.dirname(pdf_path),
                os.path.splitext(os.path.basename(docx_path))[0] + ".pdf"
            )

            if os.path.exists(expected_pdf):
                return expected_pdf
            elif os.path.exists(pdf_path):
                return pdf_path
            else:
                print(f"[PDF转换] LibreOffice 转换失败: {result.stderr}")
                return None

        except subprocess.TimeoutExpired:
            print("[PDF转换] LibreOffice 转换超时")
            return None
        except Exception as e:
            print(f"[PDF转换] 转换失败: {e}")
            return None

    def print_file(self, file_path, printer_name=None):
        """
        打印文件（自动转换 docx 为 PDF 再打印）

        Args:
            file_path: 要打印的文件路径
            printer_name: 打印机名称（可选）

        Returns:
            {"success": True, "job_id": "..."}
            或
            {"success": False, "error": "错误信息"}
        """
        import shutil

        target_printer = printer_name or self.printer_name

        # 确保文件存在
        abs_path = os.path.abspath(os.path.expanduser(file_path))
        print(f"[打印] 文件绝对路径: {abs_path}")
        print(f"[打印] 文件存在: {os.path.exists(abs_path)}")

        # 确定文件类型并转换
        pdf_path = None
        if abs_path.endswith('.docx'):
            print("[打印] 检测到 docx 文件，使用 LibreOffice 转换为 PDF...")
            pdf_path = self.docx_to_pdf(abs_path)
            if not pdf_path:
                return {"success": False, "error": "docx 转换为 PDF 失败"}
            print(f"[打印] PDF 生成成功: {pdf_path}")
            file_to_print = pdf_path
        else:
            file_to_print = abs_path

        # 使用 lp 打印 PDF
        # -o sides=one-sided 单面打印
        # -o orientation-requested=5 横向打印
        cmd = ["lp"]
        if target_printer:
            cmd.extend(["-d", target_printer])
        cmd.extend(["-o", "sides=one-sided", "-o", "orientation-requested=5"])
        cmd.append(file_to_print)

        print(f"[打印] 命令: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )

            print(f"[打印] 返回码: {result.returncode}")
            print(f"[打印] stdout: {result.stdout}")
            print(f"[打印] stderr: {result.stderr}")

            # 清理临时 PDF 文件
            if abs_path.endswith('.docx') and pdf_path:
                try:
                    os.unlink(pdf_path)
                except:
                    pass

            if result.returncode == 0:
                job_id = result.stdout.strip() if result.stdout else "unknown"
                return {
                    "success": True,
                    "job_id": job_id,
                    "printer": target_printer or self.get_default_printer() or "default"
                }
            else:
                return {
                    "success": False,
                    "error": result.stderr or "打印失败"
                }

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "打印超时"}
        except FileNotFoundError:
            return {"success": False, "error": "找不到 lp 命令"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def check_print_status(self, job_id, printer_name=None):
        """检查打印任务状态"""
        target_printer = printer_name or self.printer_name

        cmd = ["lpq"]
        if target_printer:
            cmd.extend(["-P", target_printer])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )

            if str(job_id) in result.stdout:
                return {"status": "printing", "output": result.stdout}
            else:
                return {"status": "completed", "output": result.stdout}

        except Exception as e:
            return {"status": "unknown", "error": str(e)}
