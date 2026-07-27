"""
Task Handler
Handles task browsing, claiming, and proof submission
"""

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db
from app.services.task_service import TaskService
from app.models.models import TaskCategory
import structlog

logger = structlog.get_logger(__name__)

router = Router()


class TaskStates(StatesGroup):
    """FSM states for task flow"""
    browsing_tasks = State()
    viewing_task = State()
    submitting_proof = State()
    entering_text_proof = State()


def get_task_categories_keyboard() -> InlineKeyboardMarkup:
    """Create task category selection keyboard"""
    keyboard = [
        [
            InlineKeyboardButton(text="🎥 ভিডিও", callback_data="task_cat_video"),
            InlineKeyboardButton(text="📱 অ্যাপ ইনস্টল", callback_data="task_cat_app_install"),
        ],
        [
            InlineKeyboardButton(text="💬 টেলিগ্রাম জয়েন", callback_data="task_cat_telegram_join"),
            InlineKeyboardButton(text="🌐 ওয়েবসাইট ভিজিট", callback_data="task_cat_website_visit"),
        ],
        [
            InlineKeyboardButton(text="📝 সার্ভে", callback_data="task_cat_survey"),
            InlineKeyboardButton(text="📱 সোশ্যাল মিডিয়া", callback_data="task_cat_social_media"),
        ],
        [
            InlineKeyboardButton(text="🔧 কাস্টম টাস্ক", callback_data="task_cat_custom"),
        ],
        [
            InlineKeyboardButton(text="📋 সব টাস্ক", callback_data="task_cat_all"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@router.message(F.text == "📋 টাস্ক দেখুন")
async def show_task_categories(message: types.Message):
    """Show task categories"""
    await message.answer(
        "<b>📋 টাস্ক ক্যাটাগরি</b>\n\n"
        "কোন ধরনের টাস্ক দেখতে চান? সিলেক্ট করুন:",
        reply_markup=get_task_categories_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("task_cat_"))
async def show_tasks_by_category(
    callback: types.CallbackQuery,
    db: AsyncSession = next(get_db())
):
    """Show tasks for selected category"""
    try:
        category_map = {
            "task_cat_video": TaskCategory.VIDEO,
            "task_cat_app_install": TaskCategory.APP_INSTALL,
            "task_cat_telegram_join": TaskCategory.TELEGRAM_JOIN,
            "task_cat_website_visit": TaskCategory.WEBSITE_VISIT,
            "task_cat_survey": TaskCategory.SURVEY,
            "task_cat_social_media": TaskCategory.SOCIAL_MEDIA,
            "task_cat_custom": TaskCategory.CUSTOM,
            "task_cat_all": None,
        }
        
        category = category_map.get(callback.data)
        task_service = TaskService(db)
        
        tasks = await task_service.get_available_tasks(
            user_id=callback.from_user.id,
            category=category,
            limit=10,
        )
        
        if not tasks:
            await callback.message.edit_text(
                "😔 এই ক্যাটাগরিতে কোন টাস্ক পাওয়া যায়নি।\n"
                "পরে আবার চেক করুন!",
                reply_markup=get_task_categories_keyboard(),
            )
            await callback.answer()
            return
        
        # Show tasks list
        for i, task in enumerate(tasks, 1):
            task_text = (
                f"<b>{i}. {task.title}</b>\n\n"
                f"💰 রিওয়ার্ড: <b>{task.reward:.2f} BDT</b>\n"
                f"⏱ সময়: {task.estimated_time_minutes} মিনিট\n"
                f"📊 ডিফিকাল্টি: {'⭐' * task.difficulty_level}\n"
                f"🎯 বাকি স্লট: {task.available_slots}/{task.total_slots}\n\n"
                f"<i>{task.description[:100]}...</i>"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="📋 টাস্ক দেখুন",
                    callback_data=f"view_task_{task.id}"
                )],
                [InlineKeyboardButton(
                    text="⚡ এখনই ক্লেইম করুন",
                    callback_data=f"claim_task_{task.id}"
                )],
            ])
            
            await callback.message.answer(
                task_text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Show tasks error: {e}", exc_info=True)
        await callback.answer("❌ টাস্ক লোড করতে সমস্যা হয়েছে।")
        await callback.message.answer("❌ এরর হয়েছে। দয়া করে আবার চেষ্টা করুন।")


@router.callback_query(F.data.startswith("view_task_"))
async def view_task_details(
    callback: types.CallbackQuery,
    db: AsyncSession = next(get_db())
):
    """View detailed task information"""
    try:
        task_id = int(callback.data.split("_")[-1])
        task_service = TaskService(db)
        
        # Get task from database
        from app.repositories.base_repo import BaseRepository
        from app.models.models import Task
        
        task_repo = BaseRepository(Task, db)
        task = await task_repo.get_by_id(task_id)
        
        if not task:
            await callback.answer("❌ টাস্ক পাওয়া যায়নি।")
            return
        
        task_text = (
            f"<b>📋 {task.title}</b>\n\n"
            f"<b>📝 বর্ণনা:</b>\n{task.description}\n\n"
            f"<b>💰 রিওয়ার্ড:</b> {task.reward:.2f} BDT\n"
            f"<b>🎁 বোনাস:</b> {task.bonus_reward:.2f} BDT\n"
            f"<b>⏱ সময়:</b> {task.estimated_time_minutes} মিনিট\n"
            f"<b>📊 লেভেল:</b> {'⭐' * task.difficulty_level}\n"
            f"<b>🎯 বাকি:</b> {task.available_slots}/{task.total_slots} স্লট\n\n"
        )
        
        if task.tutorial_text:
            task_text += f"<b>📖 টিউটোরিয়াল:</b>\n{task.tutorial_text}\n\n"
        
        if task.requirements:
            task_text += "<b>✅ রিকোয়ারমেন্ট:</b>\n"
            for req in task.requirements:
                task_text += f"• {req}\n"
            task_text += "\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="⚡ এখনই ক্লেইম করুন",
                callback_data=f"claim_task_{task.id}"
            )],
            [InlineKeyboardButton(
                text="🔙 ফিরে যান",
                callback_data="task_cat_all"
            )],
        ])
        
        await callback.message.edit_text(
            task_text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        
    except Exception as e:
        logger.error(f"View task error: {e}", exc_info=True)
        await callback.answer("❌ টাস্ক লোড করতে সমস্যা হয়েছে।")


@router.callback_query(F.data.startswith("claim_task_"))
async def claim_task_handler(
    callback: types.CallbackQuery,
    db: AsyncSession = next(get_db())
):
    """
    Handle task claiming with atomic locking
    Implements SELECT FOR UPDATE for race condition prevention
    """
    try:
        task_id = int(callback.data.split("_")[-1])
        user_id = callback.from_user.id
        
        # Show loading
        await callback.answer("⏳ টাস্ক ক্লেইম করা হচ্ছে...")
        
        task_service = TaskService(db)
        success, message, claim = await task_service.claim_task(
            telegram_id=user_id,
            task_id=task_id,
        )
        
        if success and claim:
            # Task claimed successfully
            success_text = (
                f"{message}\n\n"
                f"📋 <b>টাস্ক ডিটেইলস:</b>\n"
                f"⏰ টাইম লিমিট: 30 মিনিট\n"
                f"⏳ এক্সপায়ার: {claim.expires_at.strftime('%I:%M %p')}\n\n"
                f"প্রুফ সাবমিট করার জন্য নিচের বাটনে ক্লিক করুন:"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="📤 প্রুফ সাবমিট করুন",
                    callback_data=f"submit_proof_{claim.id}"
                )],
                [InlineKeyboardButton(
                    text="🔙 মেইন মেনু",
                    callback_data="back_to_main"
                )],
            ])
            
            await callback.message.edit_text(
                success_text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
        else:
            # Task claim failed
            await callback.message.edit_text(
                f"{message}\n\n"
                "অন্য টাস্ক দেখুন:",
                reply_markup=get_task_categories_keyboard(),
            )
        
    except Exception as e:
        logger.error(f"Claim task error: {e}", exc_info=True)
        await callback.answer("❌ টাস্ক ক্লেইম করতে সমস্যা হয়েছে।")
        await callback.message.answer(
            "❌ কিছু সমস্যা হয়েছে। দয়া করে আবার চেষ্টা করুন।",
            reply_markup=get_task_categories_keyboard(),
        )


@router.callback_query(F.data.startswith("submit_proof_"))
async def submit_proof_handler(
    callback: types.CallbackQuery,
    state: FSMContext,
):
    """Handle proof submission"""
    try:
        claim_id = int(callback.data.split("_")[-1])
        
        # Store claim ID in state
        await state.update_data(claim_id=claim_id)
        await state.set_state(TaskStates.submitting_proof)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🖼 ইমেজ", callback_data="proof_type_image")],
            [InlineKeyboardButton(text="🎥 ভিডিও", callback_data="proof_type_video")],
            [InlineKeyboardButton(text="📄 ডকুমেন্ট", callback_data="proof_type_document")],
            [InlineKeyboardButton(text="🔗 লিংক", callback_data="proof_type_link")],
            [InlineKeyboardButton(text="📝 টেক্সট", callback_data="proof_type_text")],
            [InlineKeyboardButton(text="🔙 ক্যান্সেল", callback_data="cancel_proof")],
        ])
        
        await callback.message.edit_text(
            "<b>📤 প্রুফ সাবমিট করুন</b>\n\n"
            "কি ধরনের প্রুফ দিতে চান? সিলেক্ট করুন:",
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        
    except Exception as e:
        logger.error(f"Submit proof error: {e}", exc_info=True)
        await callback.answer("❌ এরর হয়েছে।")
