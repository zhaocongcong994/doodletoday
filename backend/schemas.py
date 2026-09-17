from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from . import styles

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, strict=True)

Style = str

class StyleRecipe(Strict):
    """A versioned, declarative future-custom-style payload; never raw CSS."""
    base_layout: str = Field(min_length=1, max_length=40)
    palette: list[str] = Field(min_length=2, max_length=5)
    decoration: list[str] = Field(max_length=5)
    typography: str = Field(min_length=1, max_length=40)
    copy_tone: str = Field(min_length=1, max_length=80)

class StyleSnapshot(Strict):
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=40)
    registry_version: int = Field(ge=1)
    recipe: StyleRecipe

def _style_id(value: str) -> str:
    return styles.require(value)

class Login(Strict):
    invite: str = Field(min_length=1, max_length=200)

class CardInput(Strict):
    states: list[str] = Field(min_length=3, max_length=3)
    memory: str = Field(default='', max_length=500)
    style: Optional[Style] = None

    @field_validator('style')
    @classmethod
    def style_valid(cls, v):
        return _style_id(v) if v is not None else v

    @field_validator('states')
    @classmethod
    def states_valid(cls, v):
        if any(not s.strip() or len(s.strip()) > 20 for s in v):
            raise ValueError('每个状态需要 1–20 字')
        return [s.strip() for s in v]

class Card(Strict):
    title: str = Field(min_length=1, max_length=24)
    subtitle: str = Field(min_length=1, max_length=70)
    tags: list[str] = Field(min_length=3, max_length=3)
    style: Style
    # Server overwrites this value from the trusted registry before rendering.
    # The optional field reserves the serialized version format for stage two.
    style_snapshot: Optional[StyleSnapshot] = None

    @field_validator('style')
    @classmethod
    def style_valid(cls, v):
        return _style_id(v)

    @field_validator('tags')
    @classmethod
    def tags_valid(cls, v):
        if any(not s.strip() or len(s.strip()) > 12 for s in v):
            raise ValueError('标签需要 1–12 字')
        return [s.strip() for s in v]

class Revision(Strict):
    base_version_id: Optional[str] = Field(default=None, pattern=r'^[a-f0-9]{32}$')
    feedback: str = Field(min_length=1, max_length=500)
    style: Optional[Style] = None

    @field_validator('style')
    @classmethod
    def style_valid(cls, v):
        return _style_id(v) if v is not None else v

class Preference(Strict):
    style: Style

    @field_validator('style')
    @classmethod
    def style_valid(cls, v):
        return _style_id(v)

class StyleCreate(Strict):
    name: str = Field(min_length=1, max_length=40)
    recipe: StyleRecipe

class StyleUpdate(Strict):
    name: Optional[str] = Field(default=None, min_length=1, max_length=40)
    recipe: Optional[StyleRecipe] = None

class StylePreview(Strict):
    recipe: StyleRecipe

class CreateStyleTool(Strict):
    """Model-facing tool payload; the server assigns the fixed name."""
    recipe: StyleRecipe

class Empty(Strict):
    pass

class Inspect(Strict):
    asset_ids: list[str] = Field(min_length=1, max_length=10)

class Questions(Strict):
    questions: list[str] = Field(min_length=1, max_length=5)
    @field_validator('questions')
    @classmethod
    def valid(cls, v):
        if any(not s.strip() or len(s)>160 for s in v):
            raise ValueError('问题长度不合法')
        return v

class Page(Strict):
    asset_ids: list[str] = Field(min_length=1, max_length=2)
    caption: str = Field(default='', max_length=90)
    caption_kind: Literal['creative', 'excerpt'] = 'creative'

class Album(Strict):
    title: str = Field(min_length=1, max_length=24)
    subtitle: str = Field(default='', max_length=70)
    pages: list[Page] = Field(min_length=1, max_length=10)

class AssetDetail(Strict):
    id: str = Field(pattern=r'^[a-f0-9]{32}$')
    date: str = Field(default='', max_length=10)
    place: str = Field(default='', max_length=40)
    rotation: Literal[0, 90, 180, 270] = 0
    crop: list[float] = Field(default_factory=lambda: [0,0,1,1], min_length=4, max_length=4)

    @field_validator('date')
    @classmethod
    def date_valid(cls, v):
        if v:
            from datetime import date
            if date.fromisoformat(v).isoformat()!=v:
                raise ValueError('日期格式应为 YYYY-MM-DD')
        return v

    @field_validator('crop')
    @classmethod
    def crop_valid(cls, v):
        x,y,w,h=v
        if not (0<=x<1 and 0<=y<1 and .05<=w<=1 and .05<=h<=1 and x+w<=1.00001 and y+h<=1.00001):
            raise ValueError('裁剪范围无效')
        return v

class Details(Strict):
    assets: list[AssetDetail] = Field(min_length=1, max_length=10)
    memory: str = Field(default='', max_length=1000)
    skip: bool = False

class AlbumEdit(Strict):
    draft: Album
    details: Details
