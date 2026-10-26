# E/Vent — Hệ thống quản lý sự kiện

Bản thực hành triển khai ứng dụng quản lý sự kiện với Flask, PostgreSQL, Docker Compose, Nginx, Prometheus, Grafana, cAdvisor, Node Exporter, Loki và Promtail.

## Chức năng demo
- Xem danh sách sự kiện và thông tin địa điểm, thời gian, giá vé, sức chứa.
- Tạo sự kiện mới.
- Đăng ký tham dự, tính tổng tiền và kiểm tra sức chứa.
- Xem danh sách đăng ký.
- Health check `/health`, metrics `/metrics`.

> Bản demo học tập chưa có đăng nhập/phân quyền thật, cổng thanh toán, QR vé, gửi email, TLS công khai hoặc kiểm soát đồng thời nâng cao. Không dùng cho dữ liệu cá nhân thật trước khi bổ sung bảo mật.

## 1. Chuẩn bị
Yêu cầu: Ubuntu, Git và Docker Engine + Docker Compose v2. Mở terminal tại thư mục dự án.

```bash
cp .env.example .env
nano .env
```

Thay tất cả mật khẩu mẫu trong `.env`. Không commit `.env` lên GitHub.

## 2. Kiểm tra và chạy
```bash
docker compose config
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 event-web
```

Mở:
- Ứng dụng: http://localhost:8080
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000
- pgAdmin (chỉ khi cần): `docker compose --profile admin up -d pgadmin`, rồi http://localhost:5050

Tài khoản Grafana lấy từ `.env`. pgAdmin kết nối PostgreSQL bằng host `db`, port `5432`, DB/user/password trong `.env`.

## 3. Kiểm tra
```bash
curl -i http://localhost:8080/health
curl -I http://localhost:8080
docker compose ps
docker compose logs --tail=100 nginx event-web db
```
Prometheus: Status → Targets; mục tiêu `event_web`, `prometheus`, `cadvisor`, `node_exporter` cần kiểm tra trạng thái thực tế. Grafana → Explore → Loki thử `{job="docker-containers"}` nếu Promtail đọc được log Docker của host.

## 4. GitHub
```bash
git init
git add .
git commit -m "feat: initial e-vent event management app"
git status
```
Tạo repository trống trên GitHub, sau đó thay URL dưới đây bằng URL repo của bạn:
```bash
git branch -M main
git remote add origin https://github.com/USERNAME/e-vent-deployment.git
git push -u origin main
```
Tạo các commit riêng cho ứng dụng/CSDL, Nginx, monitoring và tài liệu. Kiểm tra `.env` không xuất hiện trong commit.

## 5. Dừng hệ thống
```bash
docker compose down
```
Lệnh trên giữ volume dữ liệu. Chỉ dùng `docker compose down -v` nếu chủ động muốn xóa dữ liệu PostgreSQL, Grafana, Prometheus và Loki.

## Cấu trúc
- `app/`: Flask, template, CSS, Dockerfile.
- `database/init.sql`: cấu trúc CSDL.
- `nginx/`: reverse proxy và security headers.
- `prometheus/`, `grafana/`: cấu hình giám sát.
- `loki/`, `promtail/`: log tập trung.
- `docker-compose.yml`: điều phối 10 dịch vụ.
