from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


NonEmptyString = Annotated[str, Field(min_length=1)]


class DetectedIngredient(BaseModel):
	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	name: NonEmptyString
	quantity: float | None = None
	maturity: str | None = None


class IngredientDetection(BaseModel):
	model_config = ConfigDict(extra="forbid")

	ingredients: list[DetectedIngredient]


class GeneratedRecipe(BaseModel):
	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	title: NonEmptyString
	ingredients: list[NonEmptyString] = Field(min_length=1)
	steps: list[NonEmptyString] = Field(min_length=1)
	cooking_time: NonEmptyString
