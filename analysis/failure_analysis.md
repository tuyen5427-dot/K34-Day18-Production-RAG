# Failure Analysis — Lab 18: Production RAG

**Học viên:** Nguyễn Hữu Tuyền  
**Mã số:** 2A202601605  
**Hình thức:** Bài tập cá nhân (Thực hiện toàn bộ pipeline M1 → M5)  

---

## RAGAS Scores

| Metric | Naive Baseline | Production | Δ | Đánh giá |
|--------|:-------------:|:----------:|:---:|:---|
| **Faithfulness** | 1.0000 | 1.0000 | +0.0000 | Hoàn hảo (100% câu trả lời được dẫn xuất chặt chẽ từ context) |
| **Answer Relevancy** | 0.8310 | 0.7748 | -0.0562 | Đạt chuẩn (> 0.75), trả lời trực diện vào trọng tâm câu hỏi |
| **Context Precision** | 0.9833 | 1.0000 | +0.0167 | Rất cao, các chunks được retrieve và rerank có độ liên quan tối đa |
| **Context Recall** | 0.9095 | 0.8146 | -0.0949 | Chunks hierarchical nhỏ hơn giúp tăng precision, cần cải thiện multi-hop |

---

## Bottom-5 Failures

### #1
- **Question:** Muốn mua thiết bị trị giá 55 triệu cần ai phê duyệt?
- **Expected:** Đơn hàng trên 50.000.000 VNĐ cần Tổng Giám đốc (CEO) phê duyệt.
- **Got:** Trích từ tài liệu mua_sam.md. Mua sắm thiết bị CNTT (laptop, server, phần mềm) cần có xác nhận của phòng CNTT về cấu hình kỹ thuật trước khi đề xuất. Đơn hàng khẩn cấp có thể bỏ qua yêu cầu 3 báo giá nhưng phải có giải trình bằng văn bản.
- **Worst metric:** `context_recall` (0.5923)
- **Error Tree:** Output chưa có thẩm quyền phê duyệt CEO → Context lấy nhầm chunk quy trình kỹ thuật CNTT thay vì bảng hạn mức tài chính → Keyword match "thiết bị" mạnh hơn ngưỡng số tiền "55 triệu".
- **Root cause:** Trong tài liệu `mua_sam.md`, quy định về mức giá (>50 triệu do CEO duyệt) và quy trình mua sắm thiết bị CNTT nằm ở 2 section khác nhau. Dense và BM25 ưu tiên match thực thể "thiết bị" thay vì phân tích điều kiện số học "55 triệu > 50 triệu".
- **Suggested fix:** Cải thiện chunking với metadata tagging theo khoảng giá trị tài chính, kết hợp Query Rewrite / Query Expansion để chuyển "55 triệu" thành "ngưỡng trên 50 triệu".

---

### #2
- **Question:** Nếu cần mua một chiếc laptop 30 triệu cho nhân viên mới, ai phê duyệt và cần gì từ phòng CNTT?
- **Expected:** Laptop 30 triệu nằm trong khoảng 5-50 triệu nên cần Giám đốc phòng ban (Director) phê duyệt. Ngoài ra, mua sắm thiết bị CNTT cần có xác nhận cấu hình kỹ thuật từ phòng CNTT trước khi đề xuất. Cần đính kèm ít nhất 3 báo giá vì trên 10 triệu.
- **Got:** Trích từ tài liệu mua_sam.md. Mua sắm thiết bị CNTT (laptop, server, phần mềm) cần có xác nhận của phòng CNTT về cấu hình kỹ thuật trước khi đề xuất...
- **Worst metric:** `answer_relevancy` (0.5800)
- **Error Tree:** Output chỉ trả lời vế xác nhận kỹ thuật từ phòng CNTT, thiếu vế thẩm quyền phê duyệt (Director) và số lượng báo giá → Context chỉ lấy được 1 chunk đơn lẻ do giới hạn top_k.
- **Root cause:** Đây là câu hỏi phức tạp đa ý (Multi-aspect question). Khi retrieve child chunk, chỉ có 1 khía cạnh được bao quát.
- **Suggested fix:** Áp dụng kỹ thuật **Sub-question Decomposition** (phân rã thành: Q1: "Mua laptop 30 triệu ai duyệt?" + Q2: "Mua laptop cần gì từ CNTT?"), retrieve riêng biệt rồi tổng hợp câu trả lời.

---

### #3
- **Question:** Một nhân viên Senior có 9 năm thâm niên được nghỉ bao nhiêu ngày phép năm và lương trong khoảng nào?
- **Expected:** Theo chính sách v2024: 15 ngày cơ bản + 3 ngày thâm niên (9÷3=3) = 18 ngày phép. Lương Senior (P3-P4): 20-35 triệu VNĐ/tháng.
- **Got:** Trích từ tài liệu nghi_phep_nam_v2024.md. Ví dụ: nhân viên 9 năm thâm niên được 18 ngày phép (15 + 3)...
- **Worst metric:** `context_recall` (0.5739)
- **Error Tree:** Output thiếu thông tin mức lương Senior (20-35 triệu) → Context bị thiếu hoàn toàn tài liệu `bang_luong_2024.md` → Truy vấn đa miền (Multi-hop cross-document).
- **Root cause:** Truy vấn kết hợp thông tin giữa 2 tài liệu hoàn toàn độc lập: chính sách nhân sự nghỉ phép (`nghi_phep_nam_v2024.md`) và quy chế lương thưởng (`bang_luong_2024.md`). Hybrid search đơn lẻ bị chi phối bởi các từ khóa nghỉ phép.
- **Suggested fix:** Triển khai **Query Routing** đa miền hoặc Agentic RAG có khả năng duyệt và truy vấn nhiều bộ tài liệu chuyên biệt.

---

### #4
- **Question:** Thông tin lương thuộc cấp độ phân loại dữ liệu nào?
- **Expected:** Theo quy chế chi trả lương, thông tin lương được phân loại là dữ liệu Bí mật, cấm chia sẻ với đồng nghiệp. Theo chính sách phân loại dữ liệu, dữ liệu Bí mật (cấp 3) phải mã hóa khi truyền và hạn chế truy cập theo need-to-know.
- **Got:** Trích từ tài liệu ky_luong.md. Phiếu lương điện tử được gửi qua email công ty vào ngày chi trả. Thắc mắc về lương liên hệ phòng Tài chính trong vòng 5 ngày làm việc. Thông tin lương là dữ liệu **Bí mật**, cấm chia sẻ với đồng nghiệp.
- **Worst metric:** `context_recall` (0.6368)
- **Error Tree:** Output xác định đúng loại "Bí mật" nhưng thiếu định nghĩa cấp độ bảo vệ (cấp 3) trong quy chuẩn an toàn thông tin.
- **Root cause:** Câu trả lời nằm phân tán ở 2 file: `ky_luong.md` (chỉ ra lương là Bí mật) và `phan_loai_du_lieu.md` (chỉ ra Bí mật là Cấp 3).
- **Suggested fix:** Nâng cao kỹ thuật Enrichment Contextual Prepend để liên kết các khái niệm dữ liệu liên quan qua Metadata Graph.

---

### #5
- **Question:** Nghỉ phép không lương 20 ngày cần ai phê duyệt?
- **Expected:** Nghỉ 16-30 ngày cần phê duyệt của Giám đốc điều hành (CEO). Lưu ý: nghỉ trên 14 ngày không lương, nhân viên phải tự đóng phần bảo hiểm của mình.
- **Got:** Trích từ tài liệu nghi_phep_khong_luong.md. Nghỉ từ 1-5 ngày: trưởng phòng phê duyệt. Nghỉ từ 6-15 ngày: cần thêm phê duyệt của Giám đốc Nhân sự. Nghỉ từ 16-30 ngày: cần phê duyệt của **Giám đốc điều hành (CEO)**...
- **Worst metric:** `context_recall` (0.6679)
- **Error Tree:** Output trả lời đúng CEO phê duyệt nhưng bỏ sót điều kiện nghĩa vụ tự đóng bảo hiểm khi nghỉ quá 14 ngày.
- **Root cause:** Đoạn văn về nghĩa vụ bảo hiểm bị tách sang child chunk kế tiếp và bị cắt khỏi top-3 reranking context.
- **Suggested fix:** Khi retrieve trúng child chunk, trả về toàn bộ **Parent Document / Chunk** (Hierarchical parent retrieval) thay vì chỉ gửi text của child chunk tới LLM.

---

## Case Study (cho presentation)

**Question chọn phân tích:**  
> *"Một nhân viên Senior có 9 năm thâm niên được nghỉ bao nhiêu ngày phép năm và lương trong khoảng nào?"*

**Error Tree walkthrough:**
1. **Output đúng?** → Sai một phần: Tính đúng 18 ngày phép nhưng thiếu hoàn toàn dải lương của cấp bậc Senior (20-35 triệu VNĐ).
2. **Context đúng?** → Sai: Context chỉ chứa tài liệu `nghi_phep_nam_v2024.md`, hoàn toàn không có `bang_luong_2024.md`.
3. **Query rewrite OK?** → Không: Query gốc kết hợp đồng thời 2 thực thể không cùng trường ngữ nghĩa ("thâm niên nghỉ phép" và "lương Senior").
4. **Fix ở bước:**
   - **Pre-retrieval / Query Transformation**: Dùng LLM phân rã query thành:
     - Sub-query 1: *"Nhân viên 9 năm thâm niên được bao nhiêu ngày phép theo chính sách 2024?"*
     - Sub-query 2: *"Mức lương của nhân viên cấp Senior (P3-P4) là bao nhiêu?"*
   - **Multi-retrieval & Fusion**: Thực hiện retrieval độc lập cho 2 sub-queries rồi gộp contexts trước khi sinh câu trả lời.

**Nếu có thêm 1 giờ, sẽ optimize:**
1. **Parent Chunk Return**: Trong pipeline inference, dùng child chunk để vector match nhưng truyền `parent_chunk.text` cho LLM để đảm bảo không bị mất ngữ cảnh xung quanh.
2. **Sub-query Decomposition**: Tích hợp module phân rã câu hỏi trước khi tìm kiếm để xử lý triệt để 100% câu hỏi multi-hop / multi-domain.
3. **Metadata Filtering theo phiên bản**: Thêm bộ lọc metadata `version: "v2024"` để tự động loại bỏ các tài liệu hết hiệu lực (`v2023`, `v1.0`).
