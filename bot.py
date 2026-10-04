"""Discord Game Bot tổng hợp: Tài Xỉu, Nuôi thú, Đoán chữ, Đố vui."""
import asyncio
import json
import os
import random
import time
import unicodedata

import discord
from discord import app_commands
from dotenv import load_dotenv

import db

load_dotenv()
rng = random.SystemRandom()  # CSPRNG của hệ điều hành, không thể can thiệp kết quả

BASE = os.path.dirname(os.path.abspath(__file__))


def load_json(name):
    with open(os.path.join(BASE, "data", name), encoding="utf-8") as f:
        return json.load(f)


# LƯU Ý: ID nội dung = vị trí trong file => chỉ THÊM vào cuối, không xóa/đổi thứ tự.
WORDS: list[str] = load_json("words.json")
QUESTIONS: list[dict] = load_json("questions.json")

intents = discord.Intents.default()
intents.message_content = True  # cần bật Privileged Intent trong Developer Portal
intents.members = True          # để lọc bảng xếp hạng theo thành viên máy chủ


class GameBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await db.init()
        await self.tree.sync()
        if len(WORDS) < 2000:
            print(f"[CẢNH BÁO] Kho từ mới có {len(WORDS)}/2000 từ.")
        if len(QUESTIONS) < 3000:
            print(f"[CẢNH BÁO] Kho câu hỏi mới có {len(QUESTIONS)}/3000 câu.")


bot = GameBot()
tree = bot.tree


# ---------------- Tiện ích ----------------
async def pick_content(guild_id: int, kind: str, pool_size: int) -> int:
    """Chọn ngẫu nhiên ID KHÔNG nằm trong 1500 ID gần nhất."""
    recent = await db.recent_ids(guild_id, kind)
    # Nếu kho nhỏ hơn hàng đợi, chỉ loại trừ tối đa (pool-1) ID mới nhất để luôn có thể chọn
    excluded = set(recent[: min(len(recent), pool_size - 1)])
    candidates = [i for i in range(pool_size) if i not in excluded]
    cid = rng.choice(candidates)
    await db.push_history(guild_id, kind, cid)
    return cid


def norm(s: str) -> str:
    s = s.replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return " ".join(s.lower().split())


def scramble(text: str) -> str:
    letters = [c for c in text if c != " "]
    for _ in range(20):
        rng.shuffle(letters)
        it = iter(letters)
        out = "".join(" " if c == " " else next(it) for c in text)
        if out != text or len(set(letters)) == 1:
            return out
    return out


def exp_bar(exp: int, total: int = 100, width: int = 10) -> str:
    filled = int(exp / total * width)
    return "█" * filled + "░" * (width - filled)


# ---------------- /taixiu ----------------
@tree.command(name="taixiu", description="Chơi Tài Xỉu bằng xu ảo")
@app_commands.describe(bet="Số xu đặt cược", choice="Tài (11-17) hoặc Xỉu (4-10)")
@app_commands.choices(choice=[
    app_commands.Choice(name="Tài", value="tai"),
    app_commands.Choice(name="Xỉu", value="xiu")])
async def taixiu(inter: discord.Interaction, bet: app_commands.Range[int, 1], choice: app_commands.Choice[str]):
    if not await db.try_debit(inter.user.id, bet):  # kiểm tra số dư + trừ nguyên tử
        u = await db.ensure_user(inter.user.id)
        return await inter.response.send_message(
            f"❌ Không đủ xu! Bạn chỉ có **{u['money']:,}** xu.", ephemeral=True)

    dice = [rng.randint(1, 6) for _ in range(3)]
    total = sum(dice)
    result = "tai" if 11 <= total <= 17 else "xiu" if 4 <= total <= 10 else None
    # Tổng 3 hoặc 18 (bộ ba 1-1-1 / 6-6-6) không thuộc Tài lẫn Xỉu theo đặc tả => nhà cái ăn.
    win = result == choice.value
    if win:
        await db.add_money(inter.user.id, bet * 2, points=1)  # hoàn cược + thưởng 100%
    u = await db.ensure_user(inter.user.id)

    label = {"tai": "TÀI", "xiu": "XỈU", None: "BỘ BA (nhà cái ăn)"}[result]
    e = discord.Embed(
        title="🎲 TÀI XỈU",
        description=f"Xúc xắc: **{dice[0]} - {dice[1]} - {dice[2]}**  =  **{total}** → **{label}**",
        color=discord.Color.green() if win else discord.Color.red())
    e.add_field(name="Bạn chọn", value=choice.name)
    e.add_field(name="Kết quả", value=f"🎉 Thắng +{bet:,} xu" if win else f"💸 Thua -{bet:,} xu")
    e.add_field(name="Số dư", value=f"{u['money']:,} xu")
    await inter.response.send_message(embed=e)


# ---------------- Nuôi thú ----------------
@tree.command(name="pet_adopt", description="Nhận nuôi một bé thú cưng")
@app_commands.describe(name="Tên thú cưng")
async def pet_adopt(inter: discord.Interaction, name: app_commands.Range[str, 1, 32]):
    if await db.create_pet(inter.user.id, name):
        await inter.response.send_message(f"🐾 Chúc mừng! Bạn đã nhận nuôi **{name}**.")
    else:
        await inter.response.send_message("Bạn đã có thú cưng rồi!", ephemeral=True)


@tree.command(name="pet_status", description="Xem thẻ thông tin thú cưng")
async def pet_status(inter: discord.Interaction):
    pet = await db.get_pet(inter.user.id)
    if not pet:
        return await inter.response.send_message("Bạn chưa có thú cưng. Dùng `/pet_adopt`.", ephemeral=True)
    e = discord.Embed(title=f"🐶 {pet['pet_name']}", color=discord.Color.orange())
    e.add_field(name="Cấp độ", value=str(pet["level"]))
    e.add_field(name="EXP", value=f"`{exp_bar(pet['exp'])}` {pet['exp']}/100", inline=False)
    if pet["last_fed_time"]:
        e.add_field(name="Cho ăn lần cuối", value=f"<t:{int(pet['last_fed_time'])}:R>")
    e.set_footer(text=inter.user.display_name)
    await inter.response.send_message(embed=e)


@tree.command(name="pet_feed", description="Cho thú cưng ăn (50 xu)")
async def pet_feed(inter: discord.Interaction):
    pet = await db.get_pet(inter.user.id)
    if not pet:
        return await inter.response.send_message("Bạn chưa có thú cưng. Dùng `/pet_adopt`.", ephemeral=True)
    if not await db.try_debit(inter.user.id, 50):
        return await inter.response.send_message("❌ Bạn cần 50 xu để cho ăn.", ephemeral=True)
    gain = rng.randint(15, 30)
    level, exp = pet["level"], pet["exp"] + gain
    leveled = exp >= 100
    if leveled:
        level += 1
        exp -= 100  # reset thanh EXP (giữ phần dư)
    await db.update_pet(inter.user.id, level, exp)
    msg = f"🍖 **{pet['pet_name']}** ăn ngon lành và nhận **+{gain} EXP**!"
    if leveled:
        msg += f"\n🎉 Lên **cấp {level}**!"
    msg += f"\n`{exp_bar(exp)}` {exp}/100"
    await inter.response.send_message(msg)


# ---------------- /doanchu ----------------
@tree.command(name="doanchu", description="Đoán chữ tiếng Việt từ các chữ cái bị xáo trộn")
async def doanchu(inter: discord.Interaction):
    gid = inter.guild_id or 0
    cid = await pick_content(gid, "word", len(WORDS))
    answer = WORDS[cid]
    e = discord.Embed(
        title="🔤 ĐOÁN CHỮ",
        description=f"Sắp xếp lại: **`{scramble(answer.upper())}`**\n⏱️ Bạn có 30 giây, gõ đáp án vào kênh!",
        color=discord.Color.blurple())
    await inter.response.send_message(embed=e)

    target = norm(answer)
    deadline = time.monotonic() + 30

    def check(m: discord.Message):
        return m.channel.id == inter.channel_id and not m.author.bot and norm(m.content) == target

    try:
        msg = await bot.wait_for("message", check=check, timeout=deadline - time.monotonic())
    except asyncio.TimeoutError:
        return await inter.followup.send(f"⌛ Hết giờ! Đáp án là **{answer}**.")
    reward = rng.randint(50, 100)
    await db.add_money(msg.author.id, reward, points=1)
    await inter.followup.send(f"✅ {msg.author.mention} đúng rồi! Đáp án: **{answer}**. Thưởng **+{reward} xu**.")


# ---------------- /dovui ----------------
class QuizView(discord.ui.View):
    def __init__(self, owner_id: int, options: list[str], correct: int):
        super().__init__(timeout=20)
        self.owner_id, self.correct, self.options = owner_id, correct, options
        self.done = False
        self.message: discord.Message | None = None
        for i, opt in enumerate(options):
            btn = discord.ui.Button(label=f"{'ABCD'[i]}. {opt}"[:80], style=discord.ButtonStyle.secondary)
            btn.callback = self._make_cb(i)
            self.add_item(btn)

    def _lock(self, chosen: int | None):
        for i, b in enumerate(self.children):
            b.disabled = True
            if i == self.correct:
                b.style = discord.ButtonStyle.success
            elif i == chosen:
                b.style = discord.ButtonStyle.danger

    def _make_cb(self, idx: int):
        async def cb(inter: discord.Interaction):
            if inter.user.id != self.owner_id:
                return await inter.response.send_message("Đây không phải câu hỏi của bạn!", ephemeral=True)
            if self.done:
                return
            self.done = True
            self._lock(idx)
            if idx == self.correct:
                await db.add_money(inter.user.id, 150, points=1)
                note = "✅ Chính xác! **+150 xu**"
            else:
                note = f"❌ Sai rồi! Đáp án đúng: **{'ABCD'[self.correct]}. {self.options[self.correct]}**"
            await inter.response.edit_message(content=note, view=self)
            self.stop()
        return cb

    async def on_timeout(self):
        if self.done or not self.message:
            return
        self.done = True
        self._lock(None)
        await self.message.edit(
            content=f"⌛ Hết giờ! Đáp án đúng: **{'ABCD'[self.correct]}. {self.options[self.correct]}**", view=self)


@tree.command(name="dovui", description="Đố vui có thưởng 150 xu")
async def dovui(inter: discord.Interaction):
    cid = await pick_content(inter.guild_id or 0, "trivia", len(QUESTIONS))
    q = QUESTIONS[cid]
    opts = list(q["options"])
    right_text = opts[q["answer"]]
    rng.shuffle(opts)  # xáo vị trí đáp án
    view = QuizView(inter.user.id, opts, opts.index(right_text))
    e = discord.Embed(title="❓ ĐỐ VUI", description=f"**{q['q']}**\n⏱️ 20 giây để trả lời",
                      color=discord.Color.gold())
    await inter.response.send_message(embed=e, view=view)
    view.message = await inter.original_response()


# ---------------- Tiện ích chung ----------------
async def _bal(inter: discord.Interaction):
    u = await db.ensure_user(inter.user.id)
    e = discord.Embed(title="💰 Ví của bạn", color=discord.Color.green())
    e.add_field(name="Xu", value=f"{u['money']:,}")
    e.add_field(name="Điểm", value=f"{u['points']:,}")
    await inter.response.send_message(embed=e, ephemeral=True)


@tree.command(name="bal", description="Xem số dư và điểm")
async def bal(inter: discord.Interaction):
    await _bal(inter)


@tree.command(name="vinam", description="Xem số dư và điểm (ví của bạn)")
async def vinam(inter: discord.Interaction):
    await _bal(inter)


async def _leaderboard(inter: discord.Interaction, kind: str):
    if not inter.guild:
        return await inter.response.send_message("Chỉ dùng được trong máy chủ.", ephemeral=True)
    ids = [m.id for m in inter.guild.members if not m.bot]
    medals = ["🥇", "🥈", "🥉"] + ["🔹"] * 7
    lines = []
    if kind == "money":
        for i, (uid, money) in enumerate(await db.top_money(ids)):
            lines.append(f"{medals[i]} <@{uid}> — **{money:,}** xu")
        title = "🏆 Top 10 giàu nhất"
    else:
        for i, (uid, name, lvl, exp) in enumerate(await db.top_pets(ids)):
            lines.append(f"{medals[i]} <@{uid}> — **{name}** (Lv.{lvl}, {exp}/100 EXP)")
        title = "🐾 Top 10 thú cưng"
    e = discord.Embed(title=title, description="\n".join(lines) or "Chưa có dữ liệu.",
                      color=discord.Color.gold())
    await inter.response.send_message(embed=e)


@tree.command(name="bxh", description="Bảng xếp hạng máy chủ")
@app_commands.choices(kind=[
    app_commands.Choice(name="Giàu nhất", value="money"),
    app_commands.Choice(name="Thú cưng cấp cao", value="pet")])
async def bxh(inter: discord.Interaction, kind: app_commands.Choice[str]):
    await _leaderboard(inter, kind.value)


@tree.command(name="leaderboard", description="Server leaderboard")
@app_commands.choices(kind=[
    app_commands.Choice(name="Richest", value="money"),
    app_commands.Choice(name="Top pets", value="pet")])
async def leaderboard(inter: discord.Interaction, kind: app_commands.Choice[str]):
    await _leaderboard(inter, kind.value)


if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("Thiếu DISCORD_TOKEN trong file .env")
    bot.run(token)
