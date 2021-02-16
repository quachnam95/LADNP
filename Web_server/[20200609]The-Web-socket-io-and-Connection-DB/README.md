Yêu cầu:
chạy file gentopo.py auto trên web server khi nhận được user_request mới.

Mô tả:
HTML: tạo ra các request có chưa thông tin vị trí trên bản đồ và bandwidth.
sau khi nhấn nút request, các thông tin này đc xử lý như sau:
vị trí được chọn ánh xạ với vị trí trong bảng regions or db và bảng devices trong db, các vị trí đc chọn sau đó được lưu vào bảng regions_of_request. bandwidth được lưu vào bảng user_request.
Trong code em có webserver là file index.js (nodejs + socket.io)
gentopo.py là flask
cần serverside chạy flask cùng với serverweb cho html
gentopo.py đã chạy nhưng html chưa đẩy được data về db.