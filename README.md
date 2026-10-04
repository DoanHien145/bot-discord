# Discord Game Bot Tổng Hợp

Bot Discord giải trí có hệ thống kinh tế (xu ảo) và các minigame: Tài Xỉu, Nuôi thú ảo, Đoán chữ, Đố vui. Viết bằng Python (`discord.py`), lưu dữ liệu bằng SQLite, dùng 100% Slash Commands.

## Tính năng

| Lệnh | Mô tả |
|------|-------|
| `/taixiu <bet> <Tài/Xỉu>` | Đặt cược xu. Thắng nhận +100% tiền cược, thua mất cược |
| `/pet_adopt <tên>` | Nhận nuôi một thú cưng (mỗi người một bé) |
| `/pet_status` | Xem thẻ thú cưng: tên, cấp độ, thanh EXP |
| `/pet_feed` | Cho ăn (50 xu), nhận ngẫu nhiên 15-30 EXP. Đủ 100 EXP lên 1 cấp |
| `/doanchu` | Đoán chữ bị xáo trộn trong 30 giây, thưởng 50-100 xu |
| `/dovui` | Đố vui 4 đáp án (nút bấm), 20 giây, thưởng 150 xu |
| `/bal`, `/vinam` | Xem số dư xu và điểm |
| `/bxh`, `/leaderboard` | Top 10 giàu nhất hoặc thú cưng cấp cao nhất |

Người chơi mới được tặng **1.000 xu**.

### Chống trùng lặp nội dung
Với `/doanchu` và `/dovui`, bot chọn ngẫu nhiên nội dung **không nằm trong 1.500 ID vừa chơi gần nhất** (tính riêng theo từng máy chủ). ID cũ nhất tự bị xóa khỏi danh sách loại trừ khi có ID mới.

### Tính công bằng
Mọi kết quả ngẫu nhiên đều dùng `random.SystemRandom` (nguồn ngẫu nhiên của hệ điều hành). Không có kết quả nào được cài sẵn.

## Cấu trúc thư mục

```
discord-game-bot/
├── bot.py              # Lệnh và logic game
├── db.py               # Truy cập SQLite (async)
├── data/
│   ├── words.json      # Kho từ cho /doanchu
│   └── questions.json  # Kho câu hỏi cho /dovui
├── requirements.txt
├── .env.example
├── Dockerfile
└── .gitignore
```

## Cài đặt

### 1. Tạo bot trên Discord
1. Vào [Discord Developer Portal](https://discord.com/developers/applications), chọn **New Application**.
2. Tab **Bot**: bấm **Reset Token** và lưu token lại.
3. Cũng ở tab **Bot**, bật **Privileged Gateway Intents**:
   - **Message Content Intent** (cần cho `/doanchu`)
   - **Server Members Intent** (cần cho bảng xếp hạng)
4. Tab **OAuth2 > URL Generator**: chọn scope `bot` và `applications.commands`, quyền `Send Messages`, `Embed Links`, `Read Message History`. Mở link được tạo để mời bot vào máy chủ.

### 2. Chạy bot

Yêu cầu Python 3.10 trở lên.

```bash
pip install -r requirements.txt
cp .env.example .env      # rồi điền DISCORD_TOKEN vào file .env
python bot.py
```

Lần chạy đầu bot sẽ tự tạo file `bot.db` và đồng bộ các slash command (có thể mất vài phút mới hiện trên Discord).

### 3. Chạy bằng Docker

```bash
docker build -t gamebot .
docker run -d --restart unless-stopped --env-file .env \
  -e DB_PATH=/data/bot.db -v gamebot_data:/data gamebot
```

Volume `gamebot_data` giúp dữ liệu không bị mất khi cập nhật container.

## Biến môi trường (`.env`)

| Biến | Bắt buộc | Mô tả |
|------|----------|-------|
| `DISCORD_TOKEN` | Có | Token của bot |
| `DB_PATH` | Không | Đường dẫn file SQLite (mặc định `bot.db`) |

> **Bảo mật:** không bao giờ commit file `.env` lên GitHub. File `.gitignore` đã chặn sẵn. Nếu lỡ lộ token, hãy Reset Token ngay.

## Bổ sung dữ liệu game

Bản kèm theo chỉ có **dữ liệu mẫu** (30 từ, 10 câu hỏi). Theo đặc tả cần tối thiểu **2.000 từ** và **3.000 câu hỏi**. Bot sẽ in cảnh báo khi khởi động nếu chưa đủ.

**Định dạng `data/words.json`:**
```json
["xin chào", "bánh mì", "cà phê sữa"]
```

**Định dạng `data/questions.json`:**
```json
[
  {
    "q": "Thủ đô của Việt Nam là gì?",
    "options": ["Hà Nội", "Huế", "Đà Nẵng", "TP.HCM"],
    "answer": 0
  }
]
```
`answer` là vị trí (bắt đầu từ 0) của đáp án đúng trong `options`. Vị trí đáp án được xáo ngẫu nhiên khi hiển thị.

> **Quan trọng:** ID nội dung chính là vị trí trong file. Chỉ **thêm vào cuối** file, không xóa hay đổi thứ tự các mục cũ, nếu không lịch sử chống trùng lặp sẽ bị lệch.

## Lưu trữ dữ liệu khi deploy

SQLite lưu trong một file (`bot.db`). Trên hosting, hãy chắc chắn file này nằm trên ổ đĩa **bền vững**, nếu không sẽ mất xu và thú cưng của người chơi mỗi lần deploy lại. Nên sao lưu định kỳ bằng cách copy file `bot.db`.

## Gợi ý host

- **VPS / Oracle Cloud Always Free:** miễn phí hoặc giá rẻ, chạy 24/7, giữ được file DB.
- **Dịch vụ host chuyên cho bot:** dễ dùng, nhớ hỏi rõ ổ đĩa có lưu lâu dài không.
- Các gói free tự ngủ khi không hoạt động (ví dụ Render free) sẽ làm bot offline.

Ví dụ chạy nền trên VPS Linux bằng `systemd` (file `/etc/systemd/system/gamebot.service`):

```ini
[Unit]
Description=Discord Game Bot
After=network.target

[Service]
WorkingDirectory=/home/ubuntu/discord-game-bot
ExecStart=/usr/bin/python3 bot.py
Restart=always
User=ubuntu

[Install]
WantedBy=multi-user.target
```

Sau đó: `sudo systemctl enable --now gamebot`.

## Xử lý sự cố

- **Slash command không hiện:** đợi vài phút sau lần chạy đầu, kiểm tra bot đã được mời với scope `applications.commands`.
- **`/doanchu` không nhận câu trả lời:** chưa bật Message Content Intent.
- **`/bxh` trống hoặc lỗi:** chưa bật Server Members Intent.
- **Lỗi `PrivilegedIntentsRequired`:** bật các intent ở bước cài đặt 1.
- **Mất dữ liệu sau khi deploy:** file `bot.db` không nằm trên ổ đĩa bền vững.

## Giấy phép

Tự do sử dụng và chỉnh sửa cho dự án của bạn.
