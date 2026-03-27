"""
パイプライン プラグイン群。

PageFetcher ステージ: LocalePlugin, ModalDismissPlugin, PreCaptureScriptPlugin
DataExtractor ステージ: StructuredDataPlugin, ShopifyPlugin, HTMLParserPlugin, OCRPlugin
Validator ステージ: ContractComparisonPlugin, EvidencePreservationPlugin
Reporter ステージ: DBStoragePlugin, ObjectStoragePlugin, AlertPlugin
"""

from src.pipeline.plugins.locale_plugin import LocalePlugin
from src.pipeline.plugins.modal_dismiss_plugin import ModalDismissPlugin
from src.pipeline.plugins.pre_capture_script_plugin import PreCaptureScriptPlugin
from src.pipeline.plugins.structured_data_plugin import StructuredDataPlugin
from src.pipeline.plugins.shopify_plugin import ShopifyPlugin
from src.pipeline.plugins.html_parser_plugin import HTMLParserPlugin
from src.pipeline.plugins.ocr_plugin import OCRPlugin
from src.pipeline.plugins.contract_comparison_plugin import ContractComparisonPlugin
from src.pipeline.plugins.evidence_preservation_plugin import EvidencePreservationPlugin
from src.pipeline.plugins.db_storage_plugin import DBStoragePlugin
from src.pipeline.plugins.object_storage_plugin import ObjectStoragePlugin
from src.pipeline.plugins.alert_plugin import AlertPlugin

__all__ = [
    "LocalePlugin",
    "ModalDismissPlugin",
    "PreCaptureScriptPlugin",
    "StructuredDataPlugin",
    "ShopifyPlugin",
    "HTMLParserPlugin",
    "OCRPlugin",
    "ContractComparisonPlugin",
    "EvidencePreservationPlugin",
    "DBStoragePlugin",
    "ObjectStoragePlugin",
    "AlertPlugin",
]
