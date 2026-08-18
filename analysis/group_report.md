# Báo Cáo Tổng Hợp — Lab 18: Production RAG

**Học viên:** Nguyễn Hữu Tuyền  
**Mã số:** 2A202601605  
**Lớp:** AICB-K34  
**Hình thức:** Bài tập cá nhân (Thực hiện toàn bộ pipeline M1 → M5)  
**Ngày:** 18/08/2026

## Phân công & Kết quả thực hiện

| Module | Chức năng thực hiện | Trạng thái | Tests pass |
|--------|---------------------|:----------:|:----------:|
| **M1: Chunking** | Semantic, Hierarchical (Parent-Child), Structure-Aware | Hoàn thành | 13/13 |
| **M2: Hybrid Search** | BM25 Tiếng Việt (underthesea) + Dense (BGE-M3) + RRF Fusion | Hoàn thành | 5/5 |
| **M3: Reranking** | Cross-Encoder (`bge-reranker-v2-m3`) top-20 → top-3 & Flashrank | Hoàn thành | 5/5 |
| **M4: Evaluation** | RAGAS 4 Metrics & Diagnostic Failure Tree Analysis | Hoàn thành | 4/4 |
| **M5: Enrichment** | Summarization, HyQA, Contextual Prepend & Auto Metadata | Hoàn thành | 10/10 |

**Tổng test pass:** 37/37 (100%)

---

## Kết quả RAGAS

| Metric | Naive Baseline | Production | Δ | Nhận xét |
|--------|:--------------:|:----------:|:---:|:---|
| **Faithfulness** | 1.0000 | 1.0000 | +0.0000 | Tối đa (Không bị hallucination) |
| **Answer Relevancy** | 0.8310 | 0.7748 | -0.0562 | Đạt mức cao (> 0.75), trả lời cô đọng |
| **Context Precision** | 0.9833 | 1.0000 | +0.0167 | Chạm mức 1.0 tuyệt đối nhờ Hybrid Search + Reranker |
| **Context Recall** | 0.9095 | 0.8146 | -0.0949 | Chunks nhỏ giúp loại bỏ nhiễu, cần bổ sung parent return |

---

## Key Findings

1. **Biggest improvement:**  
   Module M2 (Hybrid Search kết hợp BM25 + Dense) cùng M3 (Cross-Encoder Reranker) nâng `Context Precision` lên mức **1.0000**. Loại bỏ hoàn toàn các chunks rác, chỉ giữ lại top-3 thông tin chuẩn xác nhất.

2. **Biggest challenge:**  
   Xử lý tiếng Việt (Vietnamese Word Segmentation) và các câu hỏi đa phần (Multi-hop cross-document questions) khi thông tin nằm phân tán ở 2-3 tài liệu độc lập (ví dụ: thâm niên và bảng lương).

3. **Surprise finding:**  
   Kỹ thuật `Hierarchical Chunking (Parent-Child)` kết hợp `Contextual Prepend (M5)` cải thiện đáng kể khả năng tìm kiếm chính xác các điều khoản chi tiết mà không làm mất ngữ cảnh xuất xứ tài liệu.

---

## Presentation Notes (5 phút)

1. **RAGAS scores (naive vs production):**
   - Naive RAG dễ lấy nhầm phiên bản cũ (v2023 thay vì v2024) hoặc tài liệu nhiễu do chỉ dùng dense cosine search đơn lẻ trên basic paragraph.
   - Production RAG đạt **Context Precision 1.0000** và **Faithfulness 1.0000**, đảm bảo câu trả lời luôn đúng sự thật và đúng phiên bản quy định.

2. **Biggest win — Module nào, tại sao:**
   - **M2 (Hybrid Search BM25 + Dense via RRF) & M3 (bge-reranker-v2-m3):** BM25 bù đắp điểm yếu của dense embedding với các thực thể số/từ khóa hiếm (như số ngày nghỉ, mã quy chế, số hiệu), trong khi Cross-Encoder chấm điểm tương quan cặp (Query, Passage) chính xác vượt trội.

3. **Case study — 1 failure, Error Tree walkthrough:**
   - *Câu hỏi:* Senior 9 năm thâm niên được nghỉ bao nhiêu ngày và dải lương bao nhiêu?
   - *Phân tích Error Tree:* Lỗi nằm ở bước Query Processing/Retrieval. Query kết hợp 2 miền tri thức (Leave Policy + Salary Grid). Hệ thống mới chỉ retrieve được tài liệu Leave Policy. Cần áp dụng *Sub-query Decomposition* để truy vấn song song cả 2 domain.

4. **Next optimization nếu có thêm 1 giờ:**
   - Hoàn thiện trả về **Parent Chunk Context** thay vì chỉ child chunk khi gửi cho LLM generator.
   - Thêm bộ lọc metadata tự động (`metadata filtering`) theo phiên bản tài liệu (`version >= 2024`).
