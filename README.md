# Discord Media Downloader

Một bot Discord đơn giản để quét và tải ảnh và video từ một kênh cụ thể vào thư mục `downloads/` cục bộ.

## Tính năng chính

- Quét lịch sử tin nhắn trong một kênh để tìm các liên kết media (ảnh, video, file đính kèm).
- Hỗ trợ định dạng ảnh: jpg, jpeg, png, gif, bmp, webp.
- Hỗ trợ định dạng video: mp4, avi, mov, mkv, webm, flv.
- Lưu lịch sử quét vào `scan_history.json` để tránh tải lại cùng các URL.
- Lưu trạng thái quét vào `scan_recovery.json` để có thể resume khi bị gián đoạn.
- Tạo thư mục lưu trữ có tên dạng: `<server>_<channel>_<timestamp>` trong `downloads/`.

## Yêu cầu

- Python 3.10+ (project sử dụng `pyproject.toml` và Poetry)
- Thư viện: `discord.py` (hoặc tương thích `discord`), `requests`

Cài đặt phụ thuộc bằng Poetry:

```powershell
poetry install
```

Hoặc nếu bạn không dùng Poetry, cài thủ công (tạo `requirements.txt` tương ứng nếu cần):

```powershell
pip install -r requirements.txt
```

> Lưu ý: Dự án chứa `pyproject.toml` và `poetry.lock` — ưu tiên dùng Poetry.

## Thiết lập Bot trên Discord

1. Tạo ứng dụng mới: https://discord.com/developers/applications
2. Trong trang ứng dụng, vào tab "Bot" và tạo bot.
3. Trong tab "OAuth2" → "URL Generator": chọn `bot` làm Scope và cấp các quyền (permissions):
	- View Channels
	- Send Messages
	- Read Message History
	- Add Reactions
4. Dùng Client ID để tạo invite link và add bot vào server của bạn.

## Cấu hình môi trường

Tạo file `.env` ở thư mục gốc và thêm token của bot:

```
DISCORD_TOKEN=YOUR_DISCORD_BOT_TOKEN
```

Quan trọng: không commit token vào git. Thêm `.env` vào `.gitignore`.

## Chạy bot

Chạy bot từ thư mục `discord_media_downloader`:

```powershell
cd .\discord_media_downloader\
poetry run python .\bot.py
```

Hoặc nếu đã cài dependencies bằng pip:

```powershell
python .\bot.py
```

Khi bot khởi động thành công, sẽ có thông báo log tương ứng (xem `discord.log`).

## Cách sử dụng - Các lệnh chính (prefix mặc định: `>` hoặc có thể dùng `\`):

- `>ping` — Kiểm tra bot còn hoạt động hay không.
- `>scan <limit>` — Quét tin nhắn trong kênh hiện tại; `limit` là số tin nhắn tối đa (ví dụ: `>scan 1000`).
- `>scan all` — Quét toàn bộ lịch sử kênh (cần cân nhắc rate limit).
- `>history` — Hiển thị lịch sử quét cho kênh.
- `>clear_history` — Xóa lịch sử quét cho kênh hiện tại.
- `>resume` — Tiếp tục một phiên quét bị gián đoạn (yêu cầu quyền admin/kiểm tra trong mã nguồn).
- `>check_recovery` — Kiểm tra trạng thái phục hồi (admin).
- `>clear_recovery` — Xóa dữ liệu phục hồi cho kênh (admin).

Lưu ý: danh sách lệnh và quyền có thể được điều chỉnh trong `discord_media_downloader/bot.py`.

## Các file quan trọng trong repository

- `discord_media_downloader/bot.py` — Mã nguồn chính.
- `scan_history.json` — Lịch sử URL đã quét per-channel.
- `scan_recovery.json` — Dữ liệu phục hồi cho các phiên quét.
- `downloads/` — Thư mục chứa các file đã tải.
- `discord.log` — File log (nếu logging bật vào file).

## Vấn đề bảo mật & lưu ý

- Giữ bí mật `DISCORD_TOKEN`.
- Khi dùng `>scan all`, hãy cân nhắc giới hạn API và thời gian chạy.
- Đảm bảo bot có quyền cần thiết trên server/kênh mục tiêu (Read Message History, View Channels).

## Gợi ý & nâng cao

- Tạo `requirements.txt` nếu bạn muốn hỗ trợ pip ngoài Poetry.
- Thêm cấu hình giới hạn kích thước tập tin, hoặc whitelist/blacklist định dạng file.
- Thêm chế độ throttle để tránh bị rate-limited bởi Discord API.

## Troubleshooting nhanh

- Bot không khởi động: kiểm tra `DISCORD_TOKEN` trong `.env` và xem `discord.log`.
- Bot không truy cập được lịch sử tin nhắn: kiểm tra quyền "Read Message History" và "View Channels".
- File không được tải: kiểm tra quyền ghi thư mục `downloads/` và logs trong `discord.log`.



