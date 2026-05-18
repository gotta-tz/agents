"""5寸照片打印 Skill."""
import time
import shutil
from pathlib import Path
from typing import List
from core.skill import BaseSkill, SkillContext, SkillResult

import sys
from pathlib import Path as P
sys.path.insert(0, str(P(__file__).parent.parent.parent))

from image_downloader import ImageDownloader
from word_generator import WordGenerator
from printer import Printer


class PhotoPrintSkill(BaseSkill):
    """5寸照片打印 Skill."""

    def __init__(self, config, lark_service):
        self.image_input_dir = config.IMAGE_INPUT_DIR
        self.word_output_dir = config.WORD_OUTPUT_DIR
        self.word_script_path = config.WORD_SCRIPT_PATH
        self.python_path = config.PYTHON_PATH
        self.timeout = config.TIMEOUT_SECONDS
        self.printer_name = config.PRINTER_NAME
        self.lark = lark_service

        self.downloader = ImageDownloader(self.image_input_dir)
        self.word_gen = WordGenerator(
            self.word_script_path, self.word_output_dir,
            self.python_path, self.timeout
        )
        self.printer = Printer(self.printer_name)

    @property
    def name(self) -> str:
        return "photo_print"

    @property
    def description(self) -> str:
        return "将图片排版成5寸照片Word文档并打印"

    @property
    def examples(self) -> List[str]:
        return ["5寸照片打印", "打印照片", "帮我打印图片"]

    async def execute(self, ctx: SkillContext) -> SkillResult:
        user_text = ctx.content.get("text", "").lower()

        if any(kw in user_text for kw in ["5寸照片打印", "5寸打印"]):
            return await self._enter_collect_mode(ctx)

        if any(kw in user_text for kw in ["可以打印", "打印"]):
            return await self._execute_print(ctx)

        if any(kw in user_text for kw in ["取消", "退出打印"]):
            return await self._cancel(ctx)

        if "帮助" in user_text or "help" in user_text:
            return SkillResult(
                success=True,
                reply="📷 请先说「5寸照片打印」开始收集模式，然后发送图片，最后说「可以打印」。"
            )

        images = ctx.skill_data.get("images", [])
        return SkillResult(
            success=True,
            reply=f"📷 已收录 {len(images)} 张图片。说「可以打印」生成 Word，「取消」放弃。"
        )

    async def _enter_collect_mode(self, ctx: SkillContext) -> SkillResult:
        batch_folder = Path(self.image_input_dir) / f"batch_{int(time.time())}"
        batch_folder.mkdir(parents=True, exist_ok=True)

        ctx.skill_data["folder"] = str(batch_folder)
        ctx.skill_data["images"] = []

        return SkillResult(
            success=True,
            reply="📷 进入5寸照片打印模式，请发送图片。发送完成后说「可以打印」。",
            data={"folder": str(batch_folder)}
        )

    async def _execute_print(self, ctx: SkillContext) -> SkillResult:
        images = ctx.skill_data.get("images", [])
        folder = ctx.skill_data.get("folder")

        if not images:
            return SkillResult(success=False, reply="没有待处理的图片")

        word_result = self.word_gen.generate(folder)
        if not word_result["success"]:
            return SkillResult(success=False,
                             reply=f"生成Word失败: {word_result.get('error')}")

        word_path = word_result["output_path"]

        print_result = self.printer.print_file(word_path)
        if not print_result["success"]:
            return SkillResult(success=False,
                             reply=f"打印失败: {print_result.get('error')}")

        shutil.rmtree(folder, ignore_errors=True)

        return SkillResult(
            success=True,
            reply=f"✅ 打印任务已完成！\n"
                  f"图片数量: {len(images)} 张\n"
                  f"打印机: {print_result.get('printer')}"
        )

    async def _cancel(self, ctx: SkillContext) -> SkillResult:
        folder = ctx.skill_data.get("folder")
        if folder:
            shutil.rmtree(folder, ignore_errors=True)

        ctx.skill_data.clear()
        return SkillResult(success=True, reply="❌ 已取消，图片已清除。")