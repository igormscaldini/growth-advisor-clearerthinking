# Mock GuidedTrack exports

`mock_gt_export.py` turns a REAL GuidedTrack CSV export (never committed; keep it in the
session scratchpad) into a mock file with the same columns, shapes and value styles but no
real person's data. Written 2026-10-14 for the AI Advisor volunteer (Javier). Usage:

    python3 -I tools_mock_data/mock_gt_export.py <real_export.csv> <out.csv> "<tool title>"

It writes `out.csv` (N_ROWS rows, every column) and `out_trimmed.csv` (columns that no
mock row fills are dropped). Rules: name/email/id-like columns always get placeholders;
categorical columns sample from the real option set only when it is clearly a fixed
menu; free text becomes "Mock free text N"; constants above 400 characters become a short
placeholder; a final leak check greps every mock cell against the real file.
Delivered files live in the Drive folder "Data for AI Advisor - files"
(id 160asOFgJnE5KENpkyXJbyRF1g54empem); the full 20-row versions are in
~/Downloads/ct_mock_data_for_javier/.
