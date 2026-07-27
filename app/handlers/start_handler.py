"""
Start Command Handler
Handles user registration, onboarding, and main menu
"""

from aiogram import Router, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
import structlog
import random
import string

from app.database.session import get_db
from app.models.models import User, Referral
from app.repositories.base_repo import BaseRepository

logger = structlog.get_logger(__name__)

router = Router()


def generate_referral_code(length: int = 8) -> str:
    """Generate unique referral code"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=length))


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Create main menu keyboard"""
    keyboard = [
        [
            KeyboardButton(text="📋 টাস্ক দেখুন"),
            KeyboardButton(text="📊 আমার টাস্ক"),
        ],
        [
            KeyboardButton(text="👤 প্রোফাইল"),
            KeyboardButton(text="💰 ওয়ালেট"),
        ],
        [
            KeyboardButton(text="👥 রেফারেল"),
            KeyboardButton(text="🏆 র‌্যাংকিং"),
        ],
        [
            KeyboardButton(text="💳 উইথড্র"),
            KeyboardButton(text="❓ হেল্প"),
        ],
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="মেনু থেকে সিলেক্ট করুন..."
    )


@router.message(CommandStart())
async def start_command(
    message: types.Message,
    state: FSMContext,
    db: AsyncSession = next(get_db())
):
    """
    Handle /start command
    Register new users and process referrals
    """
    try:
        telegram_id = message.from_user.id
        username = message.from_user.username
        first_name = message.from_user.first_name
        last_name = message.from_user.last_name
        
        # Check if user exists
        user_repo = BaseRepository(User, db)
        user = await user_repo.get_by_field("telegram_id", telegram_id)
        
        if not user:
            # New user registration
            referral_code = generate_referral_code()
            
            # Check if referred by someone
            referred_by = None
            args = message.text.split()
            if len(args) > 1:
                ref_code = args[1]
                referrer = await user_repo.get_by_field("referral_code", ref_code)
                if referrer and referrer.telegram_id != telegram_id:  # Prevent self-referral
                    referred_by = referrer.id
            
            # Create user
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name or "User",
                last_name=last_name,
                referral_code=referral_code,
                referred_by=referred_by,
                current_rank="bronze",
            )
            db.add(user)
            await db.flush()
            await db.refresh(user)
            
            # Process referral if exists
            if referred_by:
                referrer = await user_repo.get_by_id(referred_by)
                if referrer:
                    # Create referral record
                    referral = Referral(
                        referrer_id=referrer.id,
                        referred_id=user.id,
                        level=1,
                    )
                    db.add(referral)
                    
                    # Update referrer stats
                    referrer.total_referrals += 1
                    referrer.active_referrals += 1
            
            await db.commit()
            
            # Welcome message
            welcome_text = (
                f"🎉 আসসালামু আলাইকুম, {first_name or 'ইউজার'}!\n\n"
                f"মাইক্রো টাস্ক প্লাটফর্মে আপনাকে স্বাগতম! 🚀\n\n"
                f"এখানে আপনি সহজ কাজ করে টাকা ইনকাম করতে পারবেন। 💰\n\n"
                f"📋 টাস্ক সম্পন্ন করুন\n"
                f"👥 বন্ধুদের রেফার করুন\n"
                f"💳 বিকাশ/নগদে টাকা তুলুন\n\n"
                f"আপনার রেফারেল কোড: <code>{referral_code}</code>\n"
                f"রেফারেল লিংক: <code>https://t.me/{message.bot.username}?start={referral_code}</code>"
            )
            
            logger.info(
                f"New user registered",
                telegram_id=telegram_id,
                username=username,
            )
            
        else:
            # Returning user
            if user.is_banned:
                await message.answer(
                    "❌ আপনার অ্যাকাউন্ট ব্লক করা হয়েছে।\n"
                    "বিস্তারিত জানতে সাপোর্টে যোগাযোগ করুন।"
                )
                return
            
            # Update last active
            user.last_active = datetime.utcnow()
            await db.commit()
            
            welcome_text = (
                f"👋 আবার স্বাগতম, {user.first_name}!\n\n"
                f"আপনার ব্যালেন্স: {user.available_balance:.2f} BDT\n"
                f"সম্পন্ন টাস্ক: {user.completed_tasks}\n"
                f"র‌্যাংক: {user.current_rank.value.upper()}\n\n"
                f"চলুন আজকের টাস্ক দেখি! 📋"
            )
        
        await message.answer(
            welcome_text,
            reply_markup=get_main_keyboard(),
            parse_mode="HTML",
        )
        
    except Exception as e:
        logger.error(
            f"Start command error",
            error=str(e),
            user_id=message.from_user.id,
            exc_info=True
        )
        await message.answer(
            "❌ কিছু সমস্যা হয়েছে। দয়া করে আবার চেষ্টা করুন।\n"
            "If problem persists, contact support."
        )


@router.message(F.text == "👤 প্রোফাইল")
async def show_profile(message: types.Message, db: AsyncSession = next(get_db())):
    """Show user profile with statistics"""
    try:
        user_repo = BaseRepository(User, db)
        user = await user_repo.get_by_field("telegram_id", message.from_user.id)
        
        if not user:
            await message.answer("❌ ইউজার পাওয়া যায়নি। /start দিন।")
            return
        
        profile_text = (
            f"<b>👤 প্রোফাইল</b>\n\n"
            f"🆔 ইউজারনেম: @{user.username or 'N/A'}\n"
            f"🆔 Telegram ID: <code>{user.telegram_id}</code>\n"
            f"🏆 র‌্যাংক: {user.current_rank.value.upper()}\n\n"
            f"<b>💰 ব্যালেন্স</b>\n"
            f"• এভেইলেবল: {user.available_balance:.2f} BDT\n"
            f"• পেন্ডিং: {user.pending_balance:.2f} BDT\n"
            f"• লাইফটাইম আর্নিং: {user.lifetime_earnings:.2f} BDT\n"
            f"• রেফারেল আর্নিং: {user.referral_earnings:.2f} BDT\n"
            f"• টোটাল উইথড্র: {user.total_withdrawn:.2f} BDT\n\n"
            f"<b>📊 টাস্ক স্ট্যাটিসটিক্স</b>\n"
            f"• কমপ্লিটেড: {user.completed_tasks}\n"
            f"• এপ্রুভড: {user.approved_tasks}\n"
            f"• রিজেক্টেড: {user.rejected_tasks}\n"
            f"• পেন্ডিং রিভিউ: {user.pending_review}\n\n"
            f"<b>👥 রেফারেল</b>\n"
            f"• টোটাল রেফারেল: {user.total_referrals}\n"
            f"• এক্টিভ রেফারেল: {user.active_referrals}\n"
            f"• রেফারেল কোড: <code>{user.referral_code}</code>\n\n"
            f"📅 জয়েনড: {user.created_at.strftime('%d/%m/%Y')}"
        )
        
        await message.answer(
            profile_text,
            parse_mode="HTML",
        )
        
    except Exception as e:
        logger.error(f"Profile error: {e}", exc_info=True)
        await message.answer("❌ প্রোফাইল লোড করতে সমস্যা হয়েছে।")


@router.message(F.text == "💰 ওয়ালেট")
async def show_wallet(message: types.Message, db: AsyncSession = next(get_db())):
    """Show wallet information"""
    try:
        user_repo = BaseRepository(User, db)
        user = await user_repo.get_by_field("telegram_id", message.from_user.id)
        
        if not user:
            await message.answer("❌ ইউজার পাওয়া যায়নি। /start দিন।")
            return
        
        wallet_text = (
            f"<b>💰 ওয়ালেট</b>\n\n"
            f"💵 এভেইলেবল ব্যালেন্স: <b>{user.available_balance:.2f} BDT</b>\n"
            f"⏳ পেন্ডিং ব্যালেন্স: <b>{user.pending_balance:.2f} BDT</b>\n\n"
            f"📊 মোট আর্নিং: <b>{user.lifetime_earnings:.2f} BDT</b>\n"
            f"💳 মোট উইথড্র: <b>{user.total_withdrawn:.2f} BDT</b>\n\n"
            f"💸 <b>উইথড্র মেথড:</b>\n"
            f"• bKash\n"
            f"• Nagad\n"
            f"• Rocket\n\n"
            f"মিনিমাম উইথড্র: <b>100 BDT</b>\n"
            f"ডেইলি লিমিট: <b>50,000 BDT</b>"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 টাকা তুলুন", callback_data="withdraw_request")],
            [InlineKeyboardButton(text="📜 ট্রানজেকশন হিস্টোরি", callback_data="tx_history")],
        ])
        
        await message.answer(
            wallet_text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
        
    except Exception as e:
        logger.error(f"Wallet error: {e}", exc_info=True)
        await message.answer("❌ ওয়ালেট লোড করতে সমস্যা হয়েছে।")
