# Individual Reflection — Lab 18: Production RAG Pipeline

**Học viên:** Nguyễn Hữu Tuyền  
**Mã số:** 2A202601605   
**Module phụ trách:** Toàn bộ Pipeline (M1 → M2 → M3 → M4 → M5)  
**Ngày:** 18/08/2026  

---

## 1. Đóng góp kỹ thuật & Mapping bài giảng

| Lecture Concept | Module | Hàm cụ thể | Observation & Kết quả thực nghiệm |
|:---|:---:|:---|:---|
| **Semantic Chunking** | M1 | `chunk_semantic()` | Dùng cosine similarity giữa các câu liên tiếp (threshold 0.85). Giúp gom trọn vẹn từng ý nghĩa mà không bị ngắt quãng giữa câu. |
| **Hierarchical Chunking** | M1 | `chunk_hierarchical()` | Chia tài liệu thành parent chunks (2048 chars) và child chunks (256 chars) có liên kết `parent_id`. Đạt hiệu năng tối ưu nhất trong lab. |
| **Structure-Aware Chunking** | M1 | `chunk_structure_aware()` | Parse markdown headers (#, ##, ###) để giữ nguyên cấu trúc bảng biểu, danh sách và section hierarchy. |
| **Vietnamese Tokenization** | M2 | `segment_vietnamese()` | Dùng `underthesea.word_tokenize` và replace `_` thành dấu cách giúp BM25 khớp chính xác từ ghép tiếng Việt. |
| **Hybrid Search & RRF** | M2 | `reciprocal_rank_fusion()` | Kết hợp BM25 (từ khóa số, mã hiệu) và Dense Vector (ngữ nghĩa) qua công thức $RRF(d) = \sum \frac{1}{k + rank + 1}$. |
| **Cross-Encoder Reranking** | M3 | `CrossEncoderReranker.rerank()` | Mô hình `BAAI/bge-reranker-v2-m3` rerank top-20 xuống top-3, đưa `Context Precision` lên mức **1.0000**. |
| **RAGAS 4 Metrics Evaluation** | M4 | `evaluate_ragas()` | Đánh giá toàn diện 4 khía cạnh: Faithfulness (1.0), Answer Relevancy (0.7748), Context Precision (1.0), Context Recall (0.8146). |
| **Diagnostic Tree Failure Analysis** | M4 | `failure_analysis()` | Tự động phân tích Bottom-N worst queries và đề xuất phương án khắc phục chuẩn xác theo Error Diagnostic Tree. |
| **Pre-retrieval Enrichment** | M5 | `_enrich_single_call()` / `enrich_chunks()` | Tối ưu hóa 1 API call / rule-based extraction để tạo Summary, HyQA questions, Contextual Prepend và Auto Metadata. |

- **Tổng số tests pass:** 37/37 tests (100% pass trên pytest).
- **Kết quả RAGAS so sánh:** Context Precision tăng từ 0.9833 lên 1.0000, Faithfulness đạt 1.0000.

---

## 2. Khó khăn & Cách giải quyết

1. **Khó khăn 1: Lỗi Tokenization với tiếng Việt trong BM25**
   - *Lỗi gặp phải:* BM25 không tìm thấy tài liệu chứa cụm từ ghép tiếng Việt (ví dụ: query "nghỉ phép" không khớp với "nghỉ_phép" do tokenizer underthesea sinh ra).
   - *Cách giải quyết:* Viết hàm tiền xử lý `segment_vietnamese()` chuẩn hóa dấu gạch dưới `_` thành dấu cách phân tách từ, giúp BM25 tính điểm từ điển chuẩn xác.

2. **Khó khăn 2: Quản lý kết nối Qdrant Vector Database trên môi trường local không có Docker daemon**
   - *Lỗi gặp phải:* `Failed to connect to docker API / ConnectionRefusedError` khi khởi tạo Qdrant Client.
   - *Cách giải quyết:* Thiết kế cơ chế Fallback thông minh: Thử kết nối đến Qdrant Server qua host/port với timeout ngắn; nếu server chưa bật thì tự động chuyển sang chế độ In-Memory `QdrantClient(location=":memory:")`. Nhờ đó pipeline và test suite chạy mượt mà độc lập.

3. **Khó khăn 3: Lỗi mã hóa ký tự Windows Console (UnicodeEncodeError cp1252)**
   - *Lỗi gặp phải:* Console Windows mặc định dùng mã hóa cp1252 báo lỗi khi in emoji hoặc chuỗi tiếng Việt có dấu.
   - *Cách giải quyết:* Cấu hình `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` ở đầu tất cả các entrypoint scripts.

---

## 3. Action Plan cho Project Thực Tế

```markdown
## Project: Hệ Thống Trợ Lý Tra Cứu Quy Chế & Văn Bản Pháp Quy Doanh Nghiệp (Enterprise Legal & Policy RAG)

### Hiện tại
- RAG pipeline hiện tại: Naive chunking (500 ký tự) + Dense embedding đơn lẻ.
- Known issues: 
  + Thường xuyên nhầm lẫn giữa các văn bản sửa đổi bổ sung (phiên bản cũ vs mới).
  + Đánh mất thông tin bảng biểu, điều khoản do cắt ngang paragraph.
  + Context Precision thấp khi gặp thuật ngữ chuyên ngành hoặc số hiệu văn bản.

### Plan áp dụng từ Lab 18
1. [x] **Chunking Strategy:** Áp dụng kết hợp Structure-Aware (theo Điều, Khoản, Điểm) và Hierarchical (Parent = Điều luật, Child = Khoản quy định).
2. [x] **Search Layer:** Triển khai Hybrid Search (BM25 với từ điển pháp lý tiếng Việt + Dense BGE-M3) hợp nhất bằng Reciprocal Rank Fusion ($k=60$).
3. [x] **Reranking:** Sử dụng `bge-reranker-v2-m3` để chọn lọc top-3 điều khoản liên quan nhất trước khi đưa vào LLM Context Window.
4. [x] **Evaluation Framework:** Xây dựng Test Set gồm 100 câu hỏi đa dạng (Lookup, Versioning, Negation, Multi-hop) và chạy benchmark định kỳ bằng RAGAS.
5. [x] **Enrichment:** Thêm Contextual Prepend (Gắn tên văn bản, số hiệu, ngày ban hành và trạng thái hiệu lực vào đầu mỗi chunk).

### Timeline triển khai
- Tuần 1: Chuẩn hóa dữ liệu văn bản, triển khai module M1 (Structure + Hierarchical Chunking) và M5 (Contextual Prepend).
- Tuần 2: Xây dựng Search Index (BM25 + Qdrant Dense) và tích hợp Cross-Encoder Reranking.
- Tuần 3: Thiết lập Pipeline RAGAS Evaluation tự động trên CI/CD, phân tích Error Tree và tối ưu hóa Prompt Template.
- Tuần 4: User Acceptance Testing (UAT) và triển khai phiên bản Production.
```

---

## 4. Tự đánh giá

| Tiêu chí | Tự chấm (1-5) | Ghi chú |
|:---|:---:|:---|
| **Hiểu bài giảng** | 5/5 | Nắm vững toàn bộ 5 modules và cơ chế hoạt động của từng kỹ thuật |
| **Code quality** | 5/5 | Code clean, type annotations, xử lý exception và fallback đầy đủ |
| **Teamwork / Independence** | 5/5 | Hoàn thành độc lập 100% các modules và test cases |
| **Problem solving** | 5/5 | Giải quyết triệt để các vấn đề về encoding, Docker fallback và tiếng Việt |
