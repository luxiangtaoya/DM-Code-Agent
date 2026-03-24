"""数据模型定义"""

from datetime import datetime, date
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field
from enum import Enum


# ==================== 枚举类型 ====================

class PriorityEnum(str, Enum):
    """优先级枚举"""
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class CaseTypeEnum(str, Enum):
    """用例类型枚举"""
    POSITIVE = "正向"
    NEGATIVE = "负向"
    EDGE = "边界"
    PERFORMANCE = "性能"
    SECURITY = "安全"


class TestStatusEnum(str, Enum):
    """测试状态枚举"""
    PENDING = "待测试"
    RUNNING = "测试中"
    PASSED = "通过"
    FAILED = "失败"
    BLOCKED = "阻塞"
    SKIPPED = "跳过"


class StatusEnum(str, Enum):
    """状态枚举"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class ResultEnum(str, Enum):
    """测试结果枚举"""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class FileTypeEnum(str, Enum):
    """文件类型枚举"""
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"


# ==================== 请求模型 ====================

class ProjectCreate(BaseModel):
    """创建项目请求"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


class ProjectUpdate(BaseModel):
    """更新项目请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    status: Optional[StatusEnum] = None


class GenerateTestCasesRequest(BaseModel):
    """生成测试用例请求"""
    model: str = Field(default="qwen3.5-flash", max_length=50)
    provider: str = Field(default="qwen", max_length=20)
    max_cases: Optional[int] = Field(None, ge=1, le=100)


class TestCaseCreate(BaseModel):
    """创建测试用例请求"""
    name: str = Field(..., min_length=1, max_length=200, description="用例名称")
    description: Optional[str] = Field(None, max_length=2000, description="用例描述")
    priority: PriorityEnum = Field(default=PriorityEnum.P1, description="用例优先级")
    case_type: CaseTypeEnum = Field(default=CaseTypeEnum.POSITIVE, description="用例类型")
    precondition: Optional[str] = Field(None, max_length=2000, description="前置条件")
    steps: str = Field(..., min_length=1, description="测试步骤")
    expected_result: str = Field(..., min_length=1, max_length=2000, description="预期结果")
    actual_result: Optional[str] = Field(None, max_length=2000, description="实际结果")
    status: TestStatusEnum = Field(default=TestStatusEnum.PENDING, description="测试状态")
    tester: Optional[str] = Field(None, max_length=100, description="测试人员")
    test_date: Optional[str] = Field(None, description="测试日期")
    tags: Optional[List[str]] = Field(default_factory=lambda: [], description="标签")


class TestCaseUpdate(BaseModel):
    """更新测试用例请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    priority: Optional[PriorityEnum] = None
    case_type: Optional[CaseTypeEnum] = None
    precondition: Optional[str] = Field(None, max_length=2000)
    steps: Optional[str] = None
    expected_result: Optional[str] = Field(None, max_length=2000)
    actual_result: Optional[str] = Field(None, max_length=2000)
    status: Optional[TestStatusEnum] = None
    tester: Optional[str] = Field(None, max_length=100)
    test_date: Optional[str] = None
    tags: Optional[List[str]] = None


class ExecuteTestCaseRequest(BaseModel):
    """执行测试用例请求"""
    provider: str = Field(default="qwen", max_length=20)
    model: str = Field(default="qwen3.5-flash", max_length=50)
    enable_screenshots: bool = Field(default=True)


class BatchExecuteRequest(BaseModel):
    """批量执行请求"""
    testcase_ids: List[int] = Field(..., min_items=1)
    provider: str = Field(default="qwen", max_length=20)
    model: str = Field(default="qwen3.5-flash", max_length=50)
    enable_screenshots: bool = Field(default=True)


class BatchDeleteRequest(BaseModel):
    """批量删除请求（用于测试用例）"""
    ids: List[int] = Field(..., min_items=1)


class BatchDeleteExecutionsRequest(BaseModel):
    """批量删除执行记录请求"""
    ids: List[str] = Field(..., min_items=1)


# ==================== 响应模型 ====================

class ApiResponse(BaseModel):
    """通用API响应"""
    code: int = Field(default=0, description="状态码，0表示成功")
    message: str = Field(default="success", description="响应消息")
    data: Optional[Any] = Field(default=None, description="响应数据")


class ProjectResponse(BaseModel):
    """项目响应"""
    id: int
    name: str
    description: Optional[str]
    status: str
    created_at: str
    updated_at: str
    test_case_count: Optional[int] = 0
    execution_count: Optional[int] = 0


class DocumentResponse(BaseModel):
    """文档响应"""
    id: int
    project_id: int
    title: str
    file_type: str
    file_size: Optional[int]
    extracted_text: Optional[str]
    created_at: str


class TestCaseResponse(BaseModel):
    """测试用例响应"""
    id: int
    project_id: int
    document_id: Optional[int]
    name: str
    description: Optional[str]
    priority: str
    case_type: str
    precondition: Optional[str]
    steps: str
    expected_result: str
    actual_result: Optional[str]
    status: str
    tester: Optional[str]
    test_date: Optional[str]
    tags: List[str]
    created_at: str
    updated_at: str


class ExecutionResponse(BaseModel):
    """执行响应"""
    id: str
    project_id: int
    testcase_id: int
    status: str
    start_time: Optional[str]
    end_time: Optional[str]
    duration: Optional[int]
    result: Optional[str]
    error_message: Optional[str]
    steps_log: Optional[List]
    screenshots: Optional[List[str]]
    gif_path: Optional[str]
    model: Optional[str]
    provider: Optional[str]


class ReportResponse(BaseModel):
    """报告响应"""
    id: int
    project_id: int
    name: str
    status: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    skipped_cases: int
    pass_rate: float
    start_time: str
    end_time: Optional[str]
    duration: Optional[int]
    created_at: str


class PaginatedResponse(BaseModel):
    """分页响应"""
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int


# ==================== WebSocket 消息模型 ====================

class WSMessage(BaseModel):
    """WebSocket消息"""
    type: str
    data: Optional[Dict] = None


class StepUpdateData(BaseModel):
    """步骤更新数据"""
    step_num: int
    thought: str
    step_abbreviation: str
    action: str
    observation: str
    timestamp: str


class ExecutionCompletedData(BaseModel):
    """执行完成数据"""
    result: str
    final_answer: Optional[str]
    gif_path: Optional[str]
    steps_log: Optional[List]


# ==================== 报告相关模型 ====================

class StatisticsFilterRequest(BaseModel):
    """统计数据筛选请求"""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: Optional[str] = None


class DefectAnalysisRequest(BaseModel):
    """缺陷分析请求"""
    execution_id: str = Field(..., description="执行记录ID")


class StatisticsResponse(BaseModel):
    """统计数据响应"""
    summary: Dict[str, int]
    status_stats: Dict[str, Any]
    execution_time_stats: Dict[str, Any]
    step_count_stats: Dict[str, Any]
    duration_stats: Dict[str, Any]
    defects: List[Dict[str, Any]]


class DefectAnalysisResponse(BaseModel):
    """缺陷分析响应"""
    analysis_id: int
    analysis_result: str
    created_at: str
