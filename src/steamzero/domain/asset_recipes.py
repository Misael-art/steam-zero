# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 SteamZero contributors
"""Receitas declarativas para derivar variantes de um único asset-fonte.

O pacote fornece somente a fonte e este contrato. O renderer confiável aplica
nodes fechados sobre alpha; QML, JavaScript, Python, shell, binários e shaders
fornecidos pelo tema nunca atravessam esta fronteira.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any

from steamzero.domain.theme_effects import EffectCost, PerformanceTier

ASSET_RECIPE_SCHEMA_VERSION = 2
MAX_ASSET_RECIPES = 32
MAX_ASSET_NODES = 12
MAX_ASSET_RECIPE_BREAKPOINTS = 32
MAX_OUTLINE_WIDTH = 32.0
MAX_PROFILE_DIMENSION = 8192
DEFAULT_CACHE_MAX_BYTES = 512 * 1024 * 1024
_RECIPE_NAME = re.compile(r"^[a-z][a-zA-Z0-9]{0,63}$")


class AssetRecipeNodeType(StrEnum):
    RECOLOR = "recolor"
    GRAYSCALE = "grayscale"
    SILHOUETTE = "silhouette"
    INVERT = "invert"
    HUE_ROTATE = "hueRotate"
    OUTLINE = "outline"
    GLOW = "glow"
    SHADOW = "shadow"


class AssetRecipeFallback(StrEnum):
    SOURCE = "source"
    OUTER = "outer"


class CachePressure(StrEnum):
    NORMAL = "normal"
    MODERATE = "moderate"
    CRITICAL = "critical"


@dataclass(frozen=True)
class _NodeRule:
    capability: str
    cost: EffectCost
    defaults: Mapping[str, Any]
    bounds: Mapping[str, tuple[float, float]]
    colors: frozenset[str] = frozenset()
    enums: Mapping[str, frozenset[str]] = field(default_factory=dict)


_NODE_RULES: dict[AssetRecipeNodeType, _NodeRule] = {
    AssetRecipeNodeType.RECOLOR: _NodeRule(
        "graphics.asset.recolor",
        EffectCost.LOW,
        {"color": "#ffffff", "opacity": 1.0},
        {"opacity": (0.0, 1.0)},
        frozenset({"color"}),
    ),
    AssetRecipeNodeType.GRAYSCALE: _NodeRule(
        "graphics.asset.grayscale",
        EffectCost.LOW,
        {"amount": 1.0},
        {"amount": (0.0, 1.0)},
    ),
    AssetRecipeNodeType.SILHOUETTE: _NodeRule(
        "graphics.asset.silhouette",
        EffectCost.LOW,
        {"color": "#000000", "opacity": 1.0},
        {"opacity": (0.0, 1.0)},
        frozenset({"color"}),
    ),
    AssetRecipeNodeType.INVERT: _NodeRule(
        "graphics.asset.invert",
        EffectCost.LOW,
        {"amount": 1.0},
        {"amount": (0.0, 1.0)},
    ),
    AssetRecipeNodeType.HUE_ROTATE: _NodeRule(
        "graphics.asset.hue-rotate",
        EffectCost.MEDIUM,
        {"degrees": 0.0},
        {"degrees": (-360.0, 360.0)},
    ),
    AssetRecipeNodeType.OUTLINE: _NodeRule(
        "graphics.asset.outline.outer",
        EffectCost.MEDIUM,
        {
            "width": 1.0,
            "color": "#ffffff",
            "opacity": 1.0,
            "position": "outer",
            "mask": "alpha",
        },
        {"width": (1.0, MAX_OUTLINE_WIDTH), "opacity": (0.0, 1.0)},
        frozenset({"color"}),
        {
            "position": frozenset({"inner", "outer"}),
            "mask": frozenset({"alpha", "sdf"}),
        },
    ),
    AssetRecipeNodeType.GLOW: _NodeRule(
        "graphics.effect.glow",
        EffectCost.HIGH,
        {"color": "#ffffff", "strength": 0.25, "blur": 16.0},
        {"strength": (0.0, 1.0), "blur": (0.0, 48.0)},
        frozenset({"color"}),
    ),
    AssetRecipeNodeType.SHADOW: _NodeRule(
        "graphics.effect.shadow",
        EffectCost.MEDIUM,
        {
            "color": "#000000",
            "opacity": 0.35,
            "blur": 12.0,
            "offsetX": 0.0,
            "offsetY": 4.0,
        },
        {
            "opacity": (0.0, 1.0),
            "blur": (0.0, 48.0),
            "offsetX": (-48.0, 48.0),
            "offsetY": (-48.0, 48.0),
        },
        frozenset({"color"}),
    ),
}

# Invert e hue rotate saem de um node builtin da engine (``AssetColorTransform``),
# que só existe quando o runtime QML traz o módulo de efeitos de cor. O node se
# declara indisponível em vez de sumir, e o renderizador publica o fallback — por
# isso a capability entra aqui e a negociação final é do runtime, não desta
# constante. Outline interno continua fora até ter node próprio.
DEFAULT_ASSET_CAPABILITIES = frozenset(
    {
        "graphics.asset.recolor",
        "graphics.asset.grayscale",
        "graphics.asset.silhouette",
        "graphics.asset.invert",
        "graphics.asset.hue-rotate",
        "graphics.asset.outline.outer",
        "graphics.effect.glow",
        "graphics.effect.shadow",
    }
)

_TIER_BUDGETS = {
    PerformanceTier.CINEMATIC: 24,
    PerformanceTier.BALANCED: 12,
    PerformanceTier.ECONOMY: 5,
    PerformanceTier.ACCESSIBLE: 5,
}


def _validate_profile_target(tier: PerformanceTier, viewport: tuple[int, int] | None) -> None:
    if not isinstance(tier, PerformanceTier):
        raise ValueError("tier do perfil inválido")
    if viewport is None:
        return
    if not isinstance(viewport, tuple) or len(viewport) != 2:
        raise ValueError("resolução do perfil precisa ser um par largura/altura")
    width, height = viewport
    if not (
        isinstance(width, int)
        and not isinstance(width, bool)
        and isinstance(height, int)
        and not isinstance(height, bool)
        and 1 <= width <= MAX_PROFILE_DIMENSION
        and 1 <= height <= MAX_PROFILE_DIMENSION
    ):
        raise ValueError("resolução do perfil fora dos limites suportados")


def asset_recipe_editor_schema() -> dict[str, Any]:
    """Public, typed controls for the Studio's allowlisted recipe inspector.

    The validator below remains authoritative. This schema only tells the UI
    which existing node fields can be edited and how to present them.
    """
    nodes: dict[str, Any] = {}
    for node_type, rule in _NODE_RULES.items():
        fields: dict[str, Any] = {}
        for name, default in rule.defaults.items():
            if name in rule.colors:
                fields[name] = {"kind": "color", "default": default}
            elif name in rule.enums:
                fields[name] = {
                    "kind": "choice",
                    "default": default,
                    "choices": sorted(rule.enums[name]),
                }
            else:
                low, high = rule.bounds[name]
                fields[name] = {
                    "kind": "number",
                    "default": default,
                    "minimum": low,
                    "maximum": high,
                    "step": 0.05 if high - low <= 2 else 1,
                }
        fields["fallback"] = {
            "kind": "choice",
            "default": "outer" if node_type is AssetRecipeNodeType.OUTLINE else "source",
            "choices": (
                ["source", "outer"] if node_type is AssetRecipeNodeType.OUTLINE else ["source"]
            ),
        }
        nodes[node_type.value] = {"fields": fields}
    return {
        "nodeTypes": [node_type.value for node_type in AssetRecipeNodeType],
        "maxRecipes": MAX_ASSET_RECIPES,
        "maxNodes": MAX_ASSET_NODES,
        "maxBreakpoints": MAX_ASSET_RECIPE_BREAKPOINTS,
        "performanceTiers": [tier.value for tier in PerformanceTier],
        "nodes": nodes,
    }


def _color(value: Any, field: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise ValueError(f"{field} precisa ser cor #RRGGBB")
    return value.lower()


def _number(value: Any, field: str, bounds: tuple[float, float]) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{field} precisa ser número")
    result = float(value)
    low, high = bounds
    if not math.isfinite(result) or not low <= result <= high:
        raise ValueError(f"{field} fora de [{low}, {high}]")
    return result


@dataclass(frozen=True)
class AssetRecipeNode:
    type: AssetRecipeNodeType
    parameters: Mapping[str, Any]
    fallback: AssetRecipeFallback = AssetRecipeFallback.SOURCE

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> AssetRecipeNode:
        try:
            node_type = AssetRecipeNodeType(payload["type"])
        except (KeyError, ValueError) as exc:
            raise ValueError("type de node desconhecido") from exc
        rule = _NODE_RULES[node_type]
        allowed = set(rule.defaults) | {"type", "fallback"}
        unknown = set(payload) - allowed
        if unknown:
            raise ValueError(f"parâmetros não permitidos para {node_type.value}: {sorted(unknown)}")
        default_fallback = "outer" if node_type is AssetRecipeNodeType.OUTLINE else "source"
        try:
            fallback = AssetRecipeFallback(payload.get("fallback", default_fallback))
        except ValueError as exc:
            raise ValueError("fallback de node desconhecido") from exc
        parameters = dict(rule.defaults)
        parameters.update(
            {key: value for key, value in payload.items() if key not in {"type", "fallback"}}
        )
        for name in rule.colors:
            parameters[name] = _color(parameters[name], name)
        for name, bounds in rule.bounds.items():
            parameters[name] = _number(parameters[name], name, bounds)
        for name, choices in rule.enums.items():
            value = parameters[name]
            if not isinstance(value, str) or value not in choices:
                raise ValueError(f"{name} precisa ser um de {sorted(choices)}")
        if node_type is AssetRecipeNodeType.SILHOUETTE and parameters["color"] not in {
            "#000000",
            "#ffffff",
        }:
            raise ValueError("silhouette aceita somente preto ou branco")
        if node_type is not AssetRecipeNodeType.OUTLINE and fallback is AssetRecipeFallback.OUTER:
            raise ValueError("fallback outer pertence somente a outline")
        return cls(node_type, parameters, fallback)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            **dict(self.parameters),
            "fallback": self.fallback.value,
        }


@dataclass(frozen=True)
class AssetRecipe:
    name: str
    source_slot: str
    nodes: tuple[AssetRecipeNode, ...]

    def node(self, node_type: AssetRecipeNodeType) -> AssetRecipeNode:
        for item in self.nodes:
            if item.type is node_type:
                return item
        raise KeyError(node_type.value)

    def to_dict(self) -> dict[str, Any]:
        return {"source": self.source_slot, "nodes": [node.to_dict() for node in self.nodes]}


@dataclass(frozen=True)
class AssetRecipeBreakpoint:
    id: str
    recipe: str
    priority: int
    min_width: int | None = None
    max_width: int | None = None
    min_height: int | None = None
    max_height: int | None = None

    @classmethod
    def from_dict(
        cls, payload: Mapping[str, Any], recipe_names: frozenset[str]
    ) -> AssetRecipeBreakpoint:
        allowed = {
            "id",
            "recipe",
            "priority",
            "minWidth",
            "maxWidth",
            "minHeight",
            "maxHeight",
        }
        unknown = set(payload) - allowed
        if unknown:
            raise ValueError(f"campos não permitidos no breakpoint: {sorted(unknown)}")
        breakpoint_id = payload.get("id")
        recipe = payload.get("recipe")
        priority = payload.get("priority")
        if not isinstance(breakpoint_id, str) or not _RECIPE_NAME.fullmatch(breakpoint_id):
            raise ValueError("id de breakpoint inválido")
        if not isinstance(recipe, str) or recipe not in recipe_names:
            raise ValueError(f"breakpoint referencia receita inexistente: {recipe}")
        if (
            isinstance(priority, bool)
            or not isinstance(priority, int)
            or not -1000 <= priority <= 1000
        ):
            raise ValueError("priority de breakpoint precisa ser inteiro entre -1000 e 1000")

        dimensions: dict[str, int | None] = {}
        for key in ("minWidth", "maxWidth", "minHeight", "maxHeight"):
            raw = payload.get(key)
            if raw is None:
                dimensions[key] = None
                continue
            if (
                isinstance(raw, bool)
                or not isinstance(raw, int)
                or not 1 <= raw <= MAX_PROFILE_DIMENSION
            ):
                raise ValueError(f"{key} precisa ser inteiro entre 1 e {MAX_PROFILE_DIMENSION}")
            dimensions[key] = raw
        if not any(value is not None for value in dimensions.values()):
            raise ValueError("breakpoint precisa declarar ao menos um limite de resolução")
        for minimum, maximum in (("minWidth", "maxWidth"), ("minHeight", "maxHeight")):
            low = dimensions[minimum]
            high = dimensions[maximum]
            if low is not None and high is not None and low > high:
                raise ValueError(f"{minimum} excede {maximum}")
        return cls(
            id=breakpoint_id,
            recipe=recipe,
            priority=priority,
            min_width=dimensions["minWidth"],
            max_width=dimensions["maxWidth"],
            min_height=dimensions["minHeight"],
            max_height=dimensions["maxHeight"],
        )

    def matches(self, width: int, height: int) -> bool:
        return (
            (self.min_width is None or width >= self.min_width)
            and (self.max_width is None or width <= self.max_width)
            and (self.min_height is None or height >= self.min_height)
            and (self.max_height is None or height <= self.max_height)
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"id": self.id, "recipe": self.recipe, "priority": self.priority}
        for name, value in (
            ("minWidth", self.min_width),
            ("maxWidth", self.max_width),
            ("minHeight", self.min_height),
            ("maxHeight", self.max_height),
        ):
            if value is not None:
                result[name] = value
        return result


@dataclass(frozen=True)
class AssetRecipeSelection:
    recipe: str
    source: str
    tier: PerformanceTier
    width: int | None = None
    height: int | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "recipe": self.recipe,
            "source": self.source,
            "tier": self.tier.value,
        }
        if self.width is not None and self.height is not None:
            result["width"] = self.width
            result["height"] = self.height
        return result


@dataclass(frozen=True)
class AssetRecipeProfiles:
    fallback: str
    tiers: Mapping[PerformanceTier, str] = field(default_factory=dict)
    breakpoints: tuple[AssetRecipeBreakpoint, ...] = ()

    @classmethod
    def from_dict(
        cls, payload: Mapping[str, Any], recipe_names: frozenset[str]
    ) -> AssetRecipeProfiles:
        unknown = set(payload) - {"fallback", "tiers", "breakpoints"}
        if unknown:
            raise ValueError(f"campos não permitidos em perfis assetRecipes: {sorted(unknown)}")
        fallback = payload.get("fallback")
        if not isinstance(fallback, str) or fallback not in recipe_names:
            raise ValueError("fallback de perfil referencia receita inexistente")
        raw_tiers = payload.get("tiers", {})
        if not isinstance(raw_tiers, Mapping):
            raise ValueError("tiers de perfil precisa ser objeto")
        tiers: dict[PerformanceTier, str] = {}
        for raw_tier, recipe in raw_tiers.items():
            try:
                tier = PerformanceTier(raw_tier)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"tier de perfil inválido: {raw_tier}") from exc
            if not isinstance(recipe, str) or recipe not in recipe_names:
                raise ValueError(f"tier {tier.value} referencia receita inexistente: {recipe}")
            tiers[tier] = recipe
        raw_breakpoints = payload.get("breakpoints", [])
        if not isinstance(raw_breakpoints, list):
            raise ValueError("breakpoints de perfil precisa ser array")
        if len(raw_breakpoints) > MAX_ASSET_RECIPE_BREAKPOINTS:
            raise ValueError(f"perfil excede {MAX_ASSET_RECIPE_BREAKPOINTS} breakpoints")
        breakpoints = tuple(
            AssetRecipeBreakpoint.from_dict(item, recipe_names)
            for item in raw_breakpoints
            if isinstance(item, Mapping)
        )
        if len(breakpoints) != len(raw_breakpoints):
            raise ValueError("cada breakpoint precisa ser objeto")
        ids = [item.id for item in breakpoints]
        priorities = [item.priority for item in breakpoints]
        if len(ids) != len(set(ids)):
            raise ValueError("id de breakpoint duplicado")
        if len(priorities) != len(set(priorities)):
            raise ValueError("priority de breakpoint duplicada; precedência ambígua")
        return cls(fallback=fallback, tiers=tiers, breakpoints=breakpoints)

    def select(
        self,
        tier: PerformanceTier,
        viewport: tuple[int, int] | None,
    ) -> AssetRecipeSelection:
        _validate_profile_target(tier, viewport)
        if viewport is not None:
            width, height = viewport
            matching = [item for item in self.breakpoints if item.matches(width, height)]
            if matching:
                selected = max(matching, key=lambda item: item.priority)
                return AssetRecipeSelection(
                    selected.recipe, f"breakpoint:{selected.id}", tier, width, height
                )
        if tier in self.tiers:
            return AssetRecipeSelection(self.tiers[tier], f"tier:{tier.value}", tier)
        return AssetRecipeSelection(self.fallback, "fallback", tier)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fallback": self.fallback,
            "tiers": {tier.value: recipe for tier, recipe in self.tiers.items()},
            "breakpoints": [item.to_dict() for item in self.breakpoints],
        }


@dataclass(frozen=True)
class AssetRecipeBook:
    source_slot: str
    recipes: Mapping[str, AssetRecipe]
    schema_version: int = ASSET_RECIPE_SCHEMA_VERSION
    profiles: AssetRecipeProfiles | None = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> AssetRecipeBook:
        unknown = set(payload) - {"schemaVersion", "sourceSlot", "recipes", "profiles"}
        if unknown:
            raise ValueError(f"campos não permitidos em assetRecipes: {sorted(unknown)}")
        schema_version = payload.get("schemaVersion")
        if (
            isinstance(schema_version, bool)
            or not isinstance(schema_version, int)
            or schema_version not in {1, 2}
        ):
            raise ValueError("schemaVersion de assetRecipes incompatível")
        if schema_version == 1 and "profiles" in payload:
            raise ValueError("profiles exige schemaVersion 2 de assetRecipes")
        if schema_version == 2 and not isinstance(payload.get("profiles"), Mapping):
            raise ValueError("schemaVersion 2 de assetRecipes exige profiles")
        source_slot = payload.get("sourceSlot")
        if not isinstance(source_slot, str) or not _RECIPE_NAME.fullmatch(source_slot):
            raise ValueError("sourceSlot de assetRecipes inválido")
        raw_recipes = payload.get("recipes")
        if not isinstance(raw_recipes, Mapping) or not raw_recipes:
            raise ValueError("recipes de assetRecipes precisa ser objeto não vazio")
        if len(raw_recipes) > MAX_ASSET_RECIPES:
            raise ValueError(f"assetRecipes excede {MAX_ASSET_RECIPES} receitas")
        recipes: dict[str, AssetRecipe] = {}
        for name, raw_recipe in raw_recipes.items():
            if not isinstance(name, str) or not _RECIPE_NAME.fullmatch(name):
                raise ValueError("nome de receita inválido")
            if not isinstance(raw_recipe, Mapping):
                raise ValueError(f"receita {name} precisa ser objeto")
            recipe_unknown = set(raw_recipe) - {"source", "nodes"}
            if recipe_unknown:
                raise ValueError(
                    f"campos não permitidos na receita {name}: {sorted(recipe_unknown)}"
                )
            recipe_source = raw_recipe.get("source")
            if recipe_source != source_slot:
                raise ValueError(f"receita {name} precisa usar a fonte única {source_slot}")
            raw_nodes = raw_recipe.get("nodes", [])
            if not isinstance(raw_nodes, list):
                raise ValueError(f"nodes da receita {name} precisa ser array")
            if len(raw_nodes) > MAX_ASSET_NODES:
                raise ValueError(f"nodes da receita {name} excede {MAX_ASSET_NODES}")
            nodes = tuple(
                AssetRecipeNode.from_dict(node) for node in raw_nodes if isinstance(node, Mapping)
            )
            if len(nodes) != len(raw_nodes):
                raise ValueError(f"node da receita {name} precisa ser objeto")
            _validate_composition(name, nodes)
            recipes[name] = AssetRecipe(name=name, source_slot=source_slot, nodes=nodes)
        raw_profiles = payload.get("profiles")
        profiles = (
            AssetRecipeProfiles.from_dict(raw_profiles, frozenset(recipes))
            if isinstance(raw_profiles, Mapping)
            else None
        )
        return cls(
            source_slot=source_slot,
            recipes=recipes,
            schema_version=int(schema_version),
            profiles=profiles,
        )

    def select_profile(
        self,
        tier: PerformanceTier,
        viewport: tuple[int, int] | None = None,
    ) -> AssetRecipeSelection:
        _validate_profile_target(tier, viewport)
        if self.profiles is not None:
            return self.profiles.select(tier, viewport)
        default_recipe = "original" if "original" in self.recipes else next(iter(self.recipes))
        return AssetRecipeSelection(default_recipe, "legacy-default", tier)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "schemaVersion": 2 if self.profiles is not None else self.schema_version,
            "sourceSlot": self.source_slot,
            "recipes": {name: recipe.to_dict() for name, recipe in self.recipes.items()},
        }
        if self.profiles is not None:
            result["profiles"] = self.profiles.to_dict()
        return result


def _validate_composition(name: str, nodes: tuple[AssetRecipeNode, ...]) -> None:
    types = [node.type for node in nodes]
    if len(types) != len(set(types)):
        raise ValueError(f"receita {name} repete node")
    color_nodes = {AssetRecipeNodeType.RECOLOR, AssetRecipeNodeType.SILHOUETTE}
    if len(color_nodes.intersection(types)) > 1:
        raise ValueError(f"receita {name} combina recolor e silhouette")
    ambient = {AssetRecipeNodeType.GLOW, AssetRecipeNodeType.SHADOW}
    if len(ambient.intersection(types)) > 1:
        raise ValueError(f"receita {name} combina glow e shadow acima do orçamento do slice")


@dataclass(frozen=True)
class ResolvedAssetNode:
    type: AssetRecipeNodeType
    parameters: Mapping[str, Any]
    capability: str
    cost: EffectCost
    fallback: AssetRecipeFallback

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "parameters": dict(self.parameters),
            "capability": self.capability,
            "cost": self.cost.value,
            "fallback": self.fallback.value,
        }


@dataclass(frozen=True)
class ResolvedAssetRecipe:
    name: str
    source_slot: str
    nodes: tuple[ResolvedAssetNode, ...]
    tier: PerformanceTier
    reduced_motion_safe: bool = True
    degraded: bool = False
    dropped_nodes: int = 0

    def node(self, node_type: AssetRecipeNodeType) -> ResolvedAssetNode:
        for item in self.nodes:
            if item.type is node_type:
                return item
        raise KeyError(node_type.value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source_slot,
            "nodes": [node.to_dict() for node in self.nodes],
            "tier": self.tier.value,
            "fallback": "source",
            "reducedMotionSafe": self.reduced_motion_safe,
            "degraded": self.degraded,
            "droppedNodes": self.dropped_nodes,
        }


@dataclass(frozen=True)
class AssetRecipeDiagnostic:
    recipe: str
    node: AssetRecipeNodeType | None
    reason: str
    fallback: str

    def to_dict(self) -> dict[str, str]:
        return {
            "recipe": self.recipe,
            "node": self.node.value if self.node is not None else "recipe",
            "reason": self.reason,
            "fallback": self.fallback,
        }


def _node_cost(node: AssetRecipeNode) -> int:
    rule = _NODE_RULES[node.type]
    base = {EffectCost.LOW: 1, EffectCost.MEDIUM: 2, EffectCost.HIGH: 3}[rule.cost]
    if node.type is AssetRecipeNodeType.OUTLINE:
        base += max(0, math.ceil(float(node.parameters["width"]) / 4.0) - 1)
    return base


def resolve_asset_recipes(
    book: AssetRecipeBook,
    *,
    capabilities: frozenset[str] = DEFAULT_ASSET_CAPABILITIES,
    tier: PerformanceTier = PerformanceTier.CINEMATIC,
    reduced_motion: bool = False,
) -> tuple[dict[str, ResolvedAssetRecipe], tuple[AssetRecipeDiagnostic, ...]]:
    """Negocia capabilities e orçamento sem nunca perder a fonte segura."""
    del reduced_motion  # todos os nodes deste slice são estáticos
    resolved: dict[str, ResolvedAssetRecipe] = {}
    diagnostics: list[AssetRecipeDiagnostic] = []
    for name, recipe in book.recipes.items():
        accepted: list[ResolvedAssetNode] = []
        fallback_to_source = False
        for node in recipe.nodes:
            rule = _NODE_RULES[node.type]
            parameters = dict(node.parameters)
            capability = rule.capability
            if node.type is AssetRecipeNodeType.OUTLINE and parameters["position"] == "inner":
                capability = "graphics.asset.outline.inner"
            if capability not in capabilities:
                if (
                    node.type is AssetRecipeNodeType.OUTLINE
                    and parameters["position"] == "inner"
                    and node.fallback is AssetRecipeFallback.OUTER
                    and "graphics.asset.outline.outer" in capabilities
                ):
                    parameters["position"] = "outer"
                    diagnostics.append(
                        AssetRecipeDiagnostic(
                            name,
                            node.type,
                            "capability ausente: graphics.asset.outline.inner",
                            "outer",
                        )
                    )
                    capability = "graphics.asset.outline.outer"
                else:
                    diagnostics.append(
                        AssetRecipeDiagnostic(
                            name,
                            node.type,
                            f"capability ausente: {capability}",
                            "source",
                        )
                    )
                    fallback_to_source = True
                    break
            accepted.append(
                ResolvedAssetNode(
                    type=node.type,
                    parameters=parameters,
                    capability=capability,
                    cost=rule.cost,
                    fallback=node.fallback,
                )
            )
        cost = sum(_node_cost(node) for node in recipe.nodes)
        if not fallback_to_source and cost > _TIER_BUDGETS[tier]:
            diagnostics.append(
                AssetRecipeDiagnostic(
                    name,
                    None,
                    f"orçamento excedido no tier {tier.value}: {cost} > {_TIER_BUDGETS[tier]}",
                    "source",
                )
            )
            fallback_to_source = True
        # A receita degradada chega vazia ao renderizador; sem este sinal o nó
        # visual não teria como distinguir "sem efeito declarado" de "efeito
        # recusado", e marcaria fallback inativo enquanto degradava.
        resolved[name] = ResolvedAssetRecipe(
            name=name,
            source_slot=recipe.source_slot,
            nodes=() if fallback_to_source else tuple(accepted),
            tier=tier,
            degraded=fallback_to_source,
            dropped_nodes=len(recipe.nodes) if fallback_to_source else 0,
        )
    return resolved, tuple(diagnostics)


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


@dataclass(frozen=True)
class PreparedAssetVariant:
    cache_key: str
    source_hash: str
    recipe_hash: str
    size: tuple[int, int]
    scale: float
    tier: PerformanceTier
    capabilities: tuple[str, ...]
    recipe: ResolvedAssetRecipe
    estimated_bytes: int
    cached: bool = True
    fallback: str = "cache"

    def to_dict(self) -> dict[str, Any]:
        return {
            "cacheKey": self.cache_key,
            "sourceHash": self.source_hash,
            "recipeHash": self.recipe_hash,
            "size": list(self.size),
            "scale": self.scale,
            "tier": self.tier.value,
            "capabilities": list(self.capabilities),
            "recipe": self.recipe.to_dict(),
            "estimatedBytes": self.estimated_bytes,
            "cached": self.cached,
            "fallback": self.fallback,
        }


class AssetRecipeCache:
    """LRU descartável de planos derivados e decodificação lógica da fonte.

    A textura física continua pertencendo ao renderer QML. Esta cache garante
    a identidade determinística e evita revalidar/decodificar a mesma fonte
    quando somente a receita muda.
    """

    def __init__(
        self,
        *,
        max_entries: int = 128,
        max_bytes: int = DEFAULT_CACHE_MAX_BYTES,
    ) -> None:
        if max_entries < 1 or max_entries > 4096:
            raise ValueError("max_entries fora de [1, 4096]")
        if max_bytes < 1 or max_bytes > DEFAULT_CACHE_MAX_BYTES:
            raise ValueError("max_bytes fora de [1, 512 MiB]")
        self._max_entries = max_entries
        self._configured_max_bytes = max_bytes
        self._pressure = CachePressure.NORMAL
        self._entries: OrderedDict[str, PreparedAssetVariant] = OrderedDict()
        self._resident_bytes = 0
        self._decoded_sources: set[str] = set()
        self.source_decodes = 0

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def configured_max_bytes(self) -> int:
        return self._configured_max_bytes

    @property
    def effective_max_bytes(self) -> int:
        factor = {
            CachePressure.NORMAL: 1.0,
            CachePressure.MODERATE: 0.5,
            CachePressure.CRITICAL: 0.25,
        }[self._pressure]
        return max(1, int(self._configured_max_bytes * factor))

    @property
    def resident_bytes(self) -> int:
        return self._resident_bytes

    def contains(self, cache_key: str) -> bool:
        return cache_key in self._entries

    def set_pressure(self, pressure: CachePressure) -> None:
        self._pressure = CachePressure(pressure)
        self._evict_until_fits()

    def _evict_one(self) -> None:
        _cache_key, removed = self._entries.popitem(last=False)
        self._resident_bytes -= removed.estimated_bytes

    def _evict_until_fits(self, *, reserve_bytes: int = 0, reserve_entries: int = 0) -> None:
        while self._entries and (
            len(self._entries) + reserve_entries > self._max_entries
            or self._resident_bytes + reserve_bytes > self.effective_max_bytes
        ):
            self._evict_one()

    def prepare(
        self,
        source: bytes,
        recipe: ResolvedAssetRecipe,
        *,
        size: tuple[int, int],
        scale: float,
        tier: PerformanceTier,
        capabilities: frozenset[str],
    ) -> PreparedAssetVariant:
        if not source:
            raise ValueError("asset-fonte vazio")
        width, height = size
        if width < 1 or height < 1 or width > 8192 or height > 8192:
            raise ValueError("tamanho de derivado fora de [1, 8192]")
        if not math.isfinite(scale) or not 0.5 <= scale <= 4.0:
            raise ValueError("escala fora de [0.5, 4.0]")
        source_hash = hashlib.sha256(source).hexdigest()
        if source_hash not in self._decoded_sources:
            validate_asset_source(source)
            self._decoded_sources.add(source_hash)
            self.source_decodes += 1
        recipe_payload = recipe.to_dict()
        recipe_hash = hashlib.sha256(_canonical_json(recipe_payload)).hexdigest()
        capability_list = tuple(sorted(capabilities))
        key_payload: dict[str, Any] = {
            "source": source_hash,
            "recipe": recipe_hash,
            "size": [width, height],
            "scale": round(float(scale), 4),
            "tier": tier.value,
            "capabilities": capability_list,
        }
        cache_key = hashlib.sha256(_canonical_json(key_payload)).hexdigest()
        cached = self._entries.get(cache_key)
        if cached is not None:
            self._entries.move_to_end(cache_key)
            return cached
        pixel_width = math.ceil(width * scale)
        pixel_height = math.ceil(height * scale)
        estimated_bytes = pixel_width * pixel_height * 4
        prepared = PreparedAssetVariant(
            cache_key=cache_key,
            source_hash=source_hash,
            recipe_hash=recipe_hash,
            size=size,
            scale=round(float(scale), 4),
            tier=tier,
            capabilities=capability_list,
            recipe=recipe,
            estimated_bytes=estimated_bytes,
        )
        if estimated_bytes > self.effective_max_bytes:
            return replace(prepared, cached=False, fallback="render-direct")
        self._evict_until_fits(reserve_bytes=estimated_bytes, reserve_entries=1)
        self._entries[cache_key] = prepared
        self._resident_bytes += estimated_bytes
        self._entries.move_to_end(cache_key)
        return prepared


#: Tipos ``data:`` aceitos dentro de um SVG. ``image/svg+xml`` fica de fora de
#: propósito: um SVG aninhado num data URI não passa por esta validação e seria
#: a porta de entrada exata que ela fecha.
_ALLOWED_DATA_PREFIXES = (
    b"data:image/png;",
    b"data:image/jpeg;",
    b"data:image/webp;",
    b"data:image/gif;",
)

#: Referências que um SVG de terceiro pode fazer. Tudo o mais é recusado: o
#: allowlist é sobre o que o tema PODE alcançar, não sobre o que sabemos ser
#: perigoso — a lista de esquemas perigosos nunca termina.
_REFERENCE = re.compile(rb"""(?:xlink:href|href|src)\s*=\s*["']([^"']*)["']""", re.IGNORECASE)
_CSS_URL = re.compile(rb"""url\(\s*['"]?([^)'"]*)['"]?\s*\)""", re.IGNORECASE)
_CSS_IMPORT = re.compile(rb"@import", re.IGNORECASE)


def _reject_external_reference(lowered: bytes) -> None:
    """Recusa referência que saia do próprio arquivo.

    Um tema de terceiro não alcança rede nem disco (AGENTS.md §10). Sem isto,
    ``<image href="https://rastreador/">`` vaza uma requisição do host do
    usuário ao renderizar, e ``file:///etc/passwd`` tenta ler arquivo local.

    Só duas formas passam, que são as que o próprio projeto usa: fragmento
    interno (``#id``) e imagem embutida (``data:image/...``). Caminho relativo
    também é recusado — ele dependeria de uma âncora que o asset não declara,
    e ``../`` a transformaria em travessia.
    """
    if _CSS_IMPORT.search(lowered):
        raise ValueError("asset SVG contém @import externo")

    for match in (*_REFERENCE.finditer(lowered), *_CSS_URL.finditer(lowered)):
        target = match.group(1).strip()
        if not target or target.startswith(b"#"):
            continue
        if target.startswith(b"data:"):
            if not target.startswith(_ALLOWED_DATA_PREFIXES):
                raise ValueError("asset SVG referencia data URI de tipo não permitido")
            continue
        raise ValueError("asset SVG referencia recurso externo ou caminho absoluto")


def validate_asset_source(source: bytes) -> None:
    """Valida a fonte antes que catálogo, cache ou renderer a consumam."""
    if not source or len(source) > 16 * 1024 * 1024:
        raise ValueError("asset-fonte vazio ou acima de 16 MiB")
    stripped = source.lstrip()
    if stripped.startswith(b"<svg") or b"<svg" in stripped[:256]:
        lowered = stripped.lower()
        prohibited = (
            b"<!doctype",
            b"<!entity",
            b"<script",
            b"<foreignobject",
            b"javascript:",
            b"data:text/html",
        )
        if any(marker in lowered for marker in prohibited):
            raise ValueError("asset SVG contém conteúdo ativo")
        if re.search(rb"\bon[a-z]+\s*=", lowered):
            raise ValueError("asset SVG contém event handler")
        _reject_external_reference(lowered)
        return
    # PNG, JPEG, WebP e AVIF são validados pelo loader confiável do Qt/Pillow
    # no adapter. O domínio ao menos rejeita conteúdo sem assinatura conhecida.
    signatures = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"RIFF", b"\x00\x00\x00")
    if not source.startswith(signatures):
        raise ValueError("formato de asset-fonte desconhecido")


def validate_retroarch_bezel_source(source: bytes) -> tuple[int, int]:
    """Validate the bounded PNG format accepted by the RetroArch overlay path."""
    validate_asset_source(source)
    if not source.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("bezel customizado do RetroArch exige PNG")
    try:
        from PIL import Image

        with Image.open(io.BytesIO(source)) as image:
            if image.format != "PNG":
                raise ValueError("o conteúdo não é uma imagem PNG")
            width, height = image.size
            if not (1 <= width <= 8192 and 1 <= height <= 8192):
                raise ValueError("as dimensões do PNG excedem o limite de 8192 px")
            image.verify()
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("o PNG do bezel está corrompido ou não pode ser decodificado") from exc
    return width, height


__all__ = [
    "ASSET_RECIPE_SCHEMA_VERSION",
    "DEFAULT_ASSET_CAPABILITIES",
    "DEFAULT_CACHE_MAX_BYTES",
    "MAX_ASSET_NODES",
    "MAX_ASSET_RECIPES",
    "MAX_OUTLINE_WIDTH",
    "AssetRecipe",
    "AssetRecipeBook",
    "AssetRecipeBreakpoint",
    "AssetRecipeCache",
    "AssetRecipeDiagnostic",
    "AssetRecipeFallback",
    "AssetRecipeNode",
    "AssetRecipeNodeType",
    "AssetRecipeProfiles",
    "AssetRecipeSelection",
    "CachePressure",
    "PreparedAssetVariant",
    "ResolvedAssetNode",
    "ResolvedAssetRecipe",
    "asset_recipe_editor_schema",
    "resolve_asset_recipes",
    "validate_asset_source",
    "validate_retroarch_bezel_source",
]
