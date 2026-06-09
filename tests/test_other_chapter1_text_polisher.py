from __future__ import annotations

from report_automation.other_proof.chapter1 import polish_chapter1_paragraph


def test_polish_removes_heading_colon():
    text = "产品定义：该系统是一类面向工业流程的三维建模工具。"
    assert polish_chapter1_paragraph(text) == "该系统是一类面向工业流程的三维建模工具。"


def test_polish_removes_nested_colon():
    text = "上游：技术组件与数据采集：该系统的上游包括传感设备和算力资源。"
    result = polish_chapter1_paragraph(text)
    assert "：" not in result
    assert ":" not in result
    assert not result.startswith("上游")


def test_polish_removes_company_name():
    text = "南京强思数字科技有限公司推出的系统适用于工业建模。"
    result = polish_chapter1_paragraph(text, company_name="南京强思数字科技有限公司")
    assert "南京强思数字科技有限公司" not in result
    assert "强思数字" not in result
