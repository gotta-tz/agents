"""Skills package - 自动注册入口."""
from typing import List


_registered_skills = []


def register_skills(host, config, lark_service) -> List[str]:
    """注册所有 Skill 到 Host.

    Args:
        host: SkillHost 实例
        config: 配置对象
        lark_service: LarkService 实例

    Returns:
        已注册的 Skill 名称列表
    """
    from skills.photo_print import PhotoPrintSkill
    from skills.general_chat import GeneralChatSkill

    # 注册 PhotoPrint Skill
    photo_skill = PhotoPrintSkill(config, lark_service)
    host.register(photo_skill)
    _registered_skills.append("photo_print")

    # 注册 GeneralChat Skill
    chat_skill = GeneralChatSkill(lark_service)
    host.register(chat_skill)
    _registered_skills.append("general_chat")

    return _registered_skills


__all__ = ["register_skills"]
