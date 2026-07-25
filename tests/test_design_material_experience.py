from __future__ import annotations

import json

from test_scene_workflow import ROOT, run_workflow_script


STATIC = ROOT / "backend" / "server" / "static"


def test_material_experience_groups_18_images_and_ranks_room_recommendations() -> None:
    module_uri = (STATIC / "scene_design_materials.js").as_uri()
    style_uri = (STATIC / "scene_style_packs.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{
          groupStylePacks,
          rankSurfaceCatalog,
        }} from {json.dumps(module_uri)};
        import {{ STYLE_PACKS }} from {json.dumps(style_uri)};

        const families = groupStylePacks(STYLE_PACKS);
        const surfaces = [
          {{
            surface_id: "paint",
            name_zh: "一般塗料",
            category: "paint",
            material_group: "塗料",
            texture_url: "/paint.png",
            usage: ["wall"],
            suitable_styles: ["scandinavian"],
          }},
          {{
            surface_id: "bath-tile",
            name_zh: "浴室止滑磚",
            category: "tile",
            material_group: "磁磚",
            texture_url: "/tile.png",
            usage: ["wall", "floor"],
            suitable_styles: ["scandinavian"],
          }},
          {{
            surface_id: "wood-floor",
            name_zh: "暖木地板",
            category: "wood",
            material_group: "木地板",
            texture_url: "/wood.png",
            usage: ["floor"],
            suitable_styles: ["scandinavian"],
          }},
        ];
        const bathroom = rankSurfaceCatalog({{
          surfaces,
          usage: "floor",
          roomType: "bathroom",
          styleId: "scandinavian_1",
        }});
        const bedroom = rankSurfaceCatalog({{
          surfaces,
          usage: "floor",
          roomType: "bedroom",
          styleId: "scandinavian_1",
        }});
        console.log(JSON.stringify({{
          familyCount: families.length,
          packCounts: families.map((family) => family.packs.length),
          allImages: families.flatMap((family) => family.packs)
            .every((pack) => pack.sourceImage.startsWith("/static/style_cards/")),
          bathroomFirst: bathroom[0],
          bedroomFirst: bedroom[0],
        }}));
        """
    )

    assert result["familyCount"] == 6
    assert result["packCounts"] == [3, 3, 3, 3, 3, 3]
    assert result["allImages"] is True
    assert result["bathroomFirst"]["surface_id"] == "bath-tile"
    assert result["bathroomFirst"]["recommended"] is True
    assert "浴室" in result["bathroomFirst"]["recommendationReason"]
    assert result["bedroomFirst"]["surface_id"] == "wood-floor"
    assert "臥室" in result["bedroomFirst"]["recommendationReason"]


def test_wet_room_floor_eligibility_rejects_unsafe_high_scoring_wood() -> None:
    module_uri = (STATIC / "scene_design_materials.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ rankSurfaceCatalog }} from {json.dumps(module_uri)};

        const stylePack = {{
          id: "scandinavian_1",
          styleId: "scandinavian",
          styleLabel: "北歐風",
          name: "自然木質",
          floor: {{ color: "#c8aa82", surfaceOption: "light_oak" }},
        }};
        const styleProfiles = {{
          scandinavian: {{
            floor_surface_ids: ["unsafe-perfect-wood", "safe-tile"],
          }},
        }};
        const surfaces = [
          {{
            surface_id: "unsafe-perfect-wood",
            name_zh: "高分天然木地板",
            category: "wood",
            material_group: "木地板",
            color_hex: "#c8aa82",
            texture_url: "/unsafe-wood.png",
            usage: ["floor"],
            suitable_styles: ["scandinavian"],
          }},
          {{
            surface_id: "safe-tile",
            name_zh: "低分防滑磁磚",
            category: "tile",
            material_group: "磁磚",
            color_hex: "#777777",
            texture_url: "/safe-tile.png",
            usage: ["floor"],
            suitable_styles: [],
          }},
        ];

        const bathroom = rankSurfaceCatalog({{
          surfaces,
          usage: "floor",
          roomType: "bathroom",
          styleId: stylePack.id,
          stylePack,
          styleProfiles,
        }});
        const balcony = rankSurfaceCatalog({{
          surfaces,
          usage: "floor",
          roomType: "balcony",
          styleId: stylePack.id,
          stylePack,
          styleProfiles,
        }});
        console.log(JSON.stringify({{
          bathroom: bathroom.map((surface) => surface.surface_id),
          balcony: balcony.map((surface) => surface.surface_id),
        }}));
        """
    )

    assert result["bathroom"] == ["safe-tile"]
    assert result["balcony"] == ["safe-tile"]


def test_wet_room_completion_rejects_inherited_and_secondary_unsafe_floor() -> None:
    module_uri = (STATIC / "scene_design_materials.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{
          isSurfaceEligibleForRoom,
          roomMaterialCompletion,
        }} from {json.dumps(module_uri)};

        const surfaces = new Map([
          ["wall-paint", {{
            surface_id: "wall-paint",
            category: "paint",
            usage: ["wall"],
          }}],
          ["unsafe-wood", {{
            surface_id: "unsafe-wood",
            category: "wood",
            usage: ["floor"],
          }}],
          ["safe-tile", {{
            surface_id: "safe-tile",
            category: "tile",
            usage: ["floor"],
          }}],
        ]);
        const lookup = (surfaceId) => surfaces.get(surfaceId) || null;
        const inheritedUnsafe = roomMaterialCompletion({{
          confirmed: true,
          surfaceOverride: {{
            wallSurfaceId: "wall-paint",
            floorSurfaceId: "unsafe-wood",
          }},
        }}, {{
          roomType: "bathroom",
          surfaceLookup: lookup,
        }});
        const unsafeSecondary = roomMaterialCompletion({{
          confirmed: true,
          surfaceOverride: {{
            wallSurfaceId: "wall-paint",
            floorSurfaceId: "safe-tile",
          }},
          materialBoundary: {{
            surface: "floor",
            mode: "free_line",
            secondarySurfaceId: "unsafe-wood",
          }},
        }}, {{
          roomType: "bathroom",
          surfaceLookup: lookup,
        }});
        const safe = roomMaterialCompletion({{
          confirmed: true,
          surfaceOverride: {{
            wallSurfaceId: "wall-paint",
            floorSurfaceId: "safe-tile",
          }},
        }}, {{
          roomType: "bathroom",
          surfaceLookup: lookup,
        }});
        console.log(JSON.stringify({{
          inheritedUnsafe,
          unsafeSecondary,
          safe,
          eligibleWoodInBedroom: isSurfaceEligibleForRoom(
            lookup("unsafe-wood"),
            "floor",
            "bedroom",
          ),
        }}));
        """
    )

    assert result["inheritedUnsafe"]["complete"] is False
    assert "floor_ineligible" in result["inheritedUnsafe"]["missing"]
    assert result["unsafeSecondary"]["complete"] is False
    assert "secondary_floor_ineligible" in result["unsafeSecondary"]["missing"]
    assert result["safe"] == {"complete": True, "missing": []}
    assert result["eligibleWoodInBedroom"] is True


def test_workbench_material_validation_blocks_unsafe_whole_house_and_room_edits() -> None:
    module_uri = (STATIC / "scene_design_materials.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ validateSurfaceSelectionForRooms }} from {json.dumps(module_uri)};

        const surfaces = new Map([
          ["paint", {{
            surface_id: "paint",
            category: "paint",
            usage: ["wall"],
          }}],
          ["wood", {{
            surface_id: "wood",
            category: "wood",
            usage: ["floor"],
          }}],
          ["tile", {{
            surface_id: "tile",
            category: "tile",
            usage: ["floor"],
          }}],
        ]);
        const rooms = [
          {{ id: "bedroom", label: "臥室", type: "bedroom" }},
          {{ id: "bathroom", label: "浴室", type: "bathroom" }},
        ];
        const validate = (targetRoomId, floorSurfaceId) => (
          validateSurfaceSelectionForRooms({{
            rooms,
            targetRoomId,
            selection: {{
              wallSurfaceId: "paint",
              floorSurfaceId,
            }},
            surfaceLookup: (surfaceId) => surfaces.get(surfaceId) || null,
          }})
        );
        console.log(JSON.stringify({{
          wholeHouseWood: validate("all", "wood"),
          bedroomWood: validate("bedroom", "wood"),
          bathroomTile: validate("bathroom", "tile"),
        }}));
        """
    )

    assert result["wholeHouseWood"]["valid"] is False
    assert result["wholeHouseWood"]["invalid"] == [
        {
            "roomId": "bathroom",
            "roomLabel": "浴室",
            "usage": "floor",
            "surfaceId": "wood",
        }
    ]
    assert result["bedroomWood"] == {"valid": True, "invalid": []}
    assert result["bathroomTile"] == {"valid": True, "invalid": []}


def test_colorway_and_floor04_room_aliases_change_the_recommended_surface_order() -> None:
    module_uri = (STATIC / "scene_design_materials.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ rankSurfaceCatalog }} from {json.dumps(module_uri)};

        const surfaces = [
          {{
            surface_id: "warm-plaster",
            name_zh: "暖米灰泥牆",
            category: "plaster",
            material_group: "礦物／灰泥",
            color_hex: "#EAD8C2",
            texture_url: "/warm-plaster.png",
            usage: ["wall"],
            suitable_styles: ["scandinavian", "wabi_sabi"],
          }},
          {{
            surface_id: "cool-concrete",
            name_zh: "冷灰清水模牆",
            category: "concrete",
            material_group: "水泥質感",
            color_hex: "#777A7D",
            texture_url: "/cool-concrete.png",
            usage: ["wall"],
            suitable_styles: ["industrial", "modern"],
          }},
          {{
            surface_id: "warm-oak",
            name_zh: "暖橡木地板",
            category: "wood",
            material_group: "木地板",
            color_hex: "#C89F72",
            texture_url: "/warm-oak.png",
            usage: ["floor"],
            suitable_styles: ["scandinavian", "wabi_sabi"],
          }},
          {{
            surface_id: "gray-tile",
            name_zh: "冷灰地磚",
            category: "tile",
            material_group: "磁磚",
            color_hex: "#777A7D",
            texture_url: "/gray-tile.png",
            usage: ["floor"],
            suitable_styles: ["industrial", "modern"],
          }},
        ];
        const styleProfiles = {{
          scandinavian: {{
            wall_surface_ids: ["warm-plaster"],
            floor_surface_ids: ["warm-oak"],
          }},
          industrial: {{
            wall_surface_ids: ["cool-concrete"],
            floor_surface_ids: ["gray-tile"],
          }},
        }};
        const warmPack = {{
          id: "scandinavian_1",
          styleId: "scandinavian",
          styleLabel: "北歐風",
          name: "自然木質",
          palette: ["#FAF4EE", "#DAAE7E", "#E0D4C8", "#7F8266"],
          wall: {{ color: "#FAF4EE", surfaceOption: "limewash" }},
          floor: {{ color: "#E0D4C8", surfaceOption: "light_oak" }},
        }};
        const coolPack = {{
          id: "industrial_3",
          styleId: "industrial",
          styleLabel: "工業風",
          name: "極簡冷調",
          palette: ["#E3DED9", "#343436", "#959493", "#747272"],
          wall: {{ color: "#747272", surfaceOption: "light_gray" }},
          floor: {{ color: "#959493", surfaceOption: "microcement" }},
        }};

        const warmDormitoryWall = rankSurfaceCatalog({{
          surfaces,
          usage: "wall",
          roomType: "dormitory",
          styleId: warmPack.id,
          stylePack: warmPack,
          styleProfiles,
        }});
        const coolDormitoryWall = rankSurfaceCatalog({{
          surfaces,
          usage: "wall",
          roomType: "dormitory",
          styleId: coolPack.id,
          stylePack: coolPack,
          styleProfiles,
        }});
        const warmDepositFloor = rankSurfaceCatalog({{
          surfaces,
          usage: "floor",
          roomType: "deposit",
          styleId: warmPack.id,
          stylePack: warmPack,
          styleProfiles,
        }});
        const coolDepositFloor = rankSurfaceCatalog({{
          surfaces,
          usage: "floor",
          roomType: "deposit",
          styleId: coolPack.id,
          stylePack: coolPack,
          styleProfiles,
        }});

        console.log(JSON.stringify({{
          warmDormitoryWall: warmDormitoryWall[0],
          coolDormitoryWall: coolDormitoryWall[0],
          warmDepositFloor: warmDepositFloor[0],
          coolDepositFloor: coolDepositFloor[0],
        }}));
        """
    )

    assert result["warmDormitoryWall"]["surface_id"] == "warm-plaster"
    assert result["coolDormitoryWall"]["surface_id"] == "cool-concrete"
    assert result["warmDepositFloor"]["surface_id"] == "warm-oak"
    assert result["coolDepositFloor"]["surface_id"] == "gray-tile"
    assert "自然木質" in result["warmDormitoryWall"]["recommendationReason"]
    assert "極簡冷調" in result["coolDormitoryWall"]["recommendationReason"]
    assert "臥室" in result["warmDormitoryWall"]["recommendationReason"]
    assert "儲藏室" in result["warmDepositFloor"]["recommendationReason"]


def test_colorways_within_the_same_style_family_change_wall_and_floor_order() -> None:
    module_uri = (STATIC / "scene_design_materials.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ rankSurfaceCatalog }} from {json.dumps(module_uri)};

        const surfaces = [
          {{
            surface_id: "light-wall",
            name_zh: "明亮暖白灰泥",
            category: "plaster",
            material_group: "礦物／灰泥",
            color_hex: "#FAF4EE",
            texture_url: "/light-wall.png",
            usage: ["wall"],
            suitable_styles: ["scandinavian", "nordic_modern"],
          }},
          {{
            surface_id: "muted-wall",
            name_zh: "低彩度灰褐灰泥",
            category: "plaster",
            material_group: "礦物／灰泥",
            color_hex: "#BAAFA3",
            texture_url: "/muted-wall.png",
            usage: ["wall"],
            suitable_styles: ["scandinavian", "nordic_modern"],
          }},
          {{
            surface_id: "light-floor",
            name_zh: "明亮淺木地板",
            category: "wood",
            material_group: "木地板",
            color_hex: "#E0D4C8",
            texture_url: "/light-floor.png",
            usage: ["floor"],
            suitable_styles: ["scandinavian", "nordic_modern"],
          }},
          {{
            surface_id: "muted-floor",
            name_zh: "低彩度深木地板",
            category: "wood",
            material_group: "木地板",
            color_hex: "#77685C",
            texture_url: "/muted-floor.png",
            usage: ["floor"],
            suitable_styles: ["scandinavian", "nordic_modern"],
          }},
        ];
        const styleProfiles = {{
          scandinavian: {{
            wall_surface_ids: ["light-wall", "muted-wall"],
            floor_surface_ids: ["light-floor", "muted-floor"],
          }},
          nordic_modern: {{
            wall_surface_ids: ["light-wall", "muted-wall"],
            floor_surface_ids: ["light-floor", "muted-floor"],
          }},
        }};
        const lightPack = {{
          id: "scandinavian_1",
          styleId: "scandinavian",
          styleLabel: "北歐風",
          name: "自然木質",
          wall: {{ color: "#FAF4EE", surfaceOption: "limewash" }},
          floor: {{ color: "#E0D4C8", surfaceOption: "light_oak" }},
        }};
        const mutedPack = {{
          id: "scandinavian_3",
          styleId: "scandinavian",
          styleLabel: "北歐風",
          name: "低彩度質感",
          wall: {{ color: "#BAAFA3", surfaceOption: "limewash" }},
          floor: {{ color: "#77685C", surfaceOption: "light_oak" }},
        }};
        const rank = (usage, stylePack) => rankSurfaceCatalog({{
          surfaces,
          usage,
          roomType: "bedroom",
          styleId: stylePack.id,
          stylePack,
          styleProfiles,
        }})[0].surface_id;

        console.log(JSON.stringify({{
          lightWall: rank("wall", lightPack),
          mutedWall: rank("wall", mutedPack),
          lightFloor: rank("floor", lightPack),
          mutedFloor: rank("floor", mutedPack),
        }}));
        """
    )

    assert result == {
        "lightWall": "light-wall",
        "mutedWall": "muted-wall",
        "lightFloor": "light-floor",
        "mutedFloor": "muted-floor",
    }


def test_material_recommendations_paginate_six_cards_without_duplicates() -> None:
    module_uri = (STATIC / "scene_design_materials.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ paginateSurfaceCatalog }} from {json.dumps(module_uri)};

        const surfaces = Array.from({{ length: 14 }}, (_, index) => ({{
          surface_id: `surface-${{index + 1}}`,
        }}));
        const first = paginateSurfaceCatalog(surfaces, {{ page: 1, pageSize: 6 }});
        const second = paginateSurfaceCatalog(surfaces, {{ page: 2, pageSize: 6 }});
        const third = paginateSurfaceCatalog(surfaces, {{ page: 3, pageSize: 6 }});
        const beforeFirst = paginateSurfaceCatalog(surfaces, {{ page: 0, pageSize: 6 }});
        const afterLast = paginateSurfaceCatalog(surfaces, {{ page: 99, pageSize: 6 }});
        console.log(JSON.stringify({{ first, second, third, beforeFirst, afterLast }}));
        """
    )

    assert len(result["first"]["items"]) == 6
    assert len(result["second"]["items"]) == 6
    assert len(result["third"]["items"]) == 2
    assert result["first"]["page"] == 1
    assert result["first"]["totalPages"] == 3
    assert result["first"]["hasPrevious"] is False
    assert result["first"]["hasNext"] is True
    assert result["second"]["hasPrevious"] is True
    assert result["second"]["hasNext"] is True
    assert result["third"]["hasPrevious"] is True
    assert result["third"]["hasNext"] is False
    assert result["beforeFirst"]["page"] == 1
    assert result["afterLast"]["page"] == 3
    ids = [
        item["surface_id"]
        for page in ("first", "second", "third")
        for item in result[page]["items"]
    ]
    assert ids == [f"surface-{index}" for index in range(1, 15)]
    assert len(ids) == len(set(ids))


def test_real_surface_catalog_changes_the_first_page_for_each_colorway() -> None:
    module_uri = (STATIC / "scene_design_materials.js").as_uri()
    style_uri = (STATIC / "scene_style_packs.js").as_uri()
    catalog_uri = (ROOT / "backend" / "catalog" / "data" / "surface_catalog.json").as_uri()
    result = run_workflow_script(
        f"""
        import {{ readFileSync }} from "node:fs";
        import {{ fileURLToPath }} from "node:url";
        import {{ rankSurfaceCatalog }} from {json.dumps(module_uri)};
        import {{ STYLE_PACKS }} from {json.dumps(style_uri)};

        const catalog = JSON.parse(readFileSync(fileURLToPath({json.dumps(catalog_uri)}), "utf8"));
        const natural = STYLE_PACKS.find((pack) => pack.id === "scandinavian_1");
        const muted = STYLE_PACKS.find((pack) => pack.id === "scandinavian_3");
        const firstPage = (usage, pack) => rankSurfaceCatalog({{
          surfaces: catalog.surfaces,
          usage,
          roomType: "dormitory",
          styleId: pack.id,
          stylePack: pack,
          styleProfiles: catalog.style_surface_profiles,
          limit: 36,
        }}).slice(0, 6).map((surface) => surface.surface_id);

        console.log(JSON.stringify({{
          naturalWall: firstPage("wall", natural),
          mutedWall: firstPage("wall", muted),
          naturalFloor: firstPage("floor", natural),
          mutedFloor: firstPage("floor", muted),
        }}));
        """
    )

    assert len(result["naturalWall"]) == 6
    assert len(result["mutedWall"]) == 6
    assert len(result["naturalFloor"]) == 6
    assert len(result["mutedFloor"]) == 6
    assert result["naturalWall"] != result["mutedWall"]
    assert result["naturalFloor"] != result["mutedFloor"]


def test_modern_minimal_stone_and_warm_oak_cards_change_floor_recommendations() -> None:
    module_uri = (STATIC / "scene_design_materials.js").as_uri()
    style_uri = (STATIC / "scene_style_packs.js").as_uri()
    catalog_uri = (ROOT / "backend" / "catalog" / "data" / "surface_catalog.json").as_uri()
    result = run_workflow_script(
        f"""
        import {{ readFileSync }} from "node:fs";
        import {{ fileURLToPath }} from "node:url";
        import {{ rankSurfaceCatalog }} from {json.dumps(module_uri)};
        import {{ STYLE_PACKS }} from {json.dumps(style_uri)};

        const catalog = JSON.parse(readFileSync(fileURLToPath({json.dumps(catalog_uri)}), "utf8"));
        const stone = STYLE_PACKS.find((pack) => pack.id === "modern_minimal_1");
        const warmOak = STYLE_PACKS.find((pack) => pack.id === "modern_minimal_2");
        const failures = [];
        for (const roomType of [
          "dormitory",
          "deposit",
          "circulation",
          "living_room",
        ]) {{
          const page = (pack) => rankSurfaceCatalog({{
            surfaces: catalog.surfaces,
            usage: "floor",
            roomType,
            styleId: pack.id,
            stylePack: pack,
            styleProfiles: catalog.style_surface_profiles,
            limit: 6,
          }}).map((surface) => surface.surface_id);
          const stoneIds = page(stone);
          const warmOakIds = page(warmOak);
          if (stoneIds.join("|") === warmOakIds.join("|")) {{
            failures.push({{ roomType, stoneIds, warmOakIds }});
          }}
        }}
        const wetSafetyFailures = [];
        for (const roomType of ["kitchen", "bathroom", "balcony"]) {{
          const ranked = rankSurfaceCatalog({{
            surfaces: catalog.surfaces,
            usage: "floor",
            roomType,
            styleId: warmOak.id,
            stylePack: warmOak,
            styleProfiles: catalog.style_surface_profiles,
            limit: 6,
          }});
          if (!ranked.every((surface) => ["tile", "wood_tile"].includes(surface.category))) {{
            wetSafetyFailures.push({{
              roomType,
              categories: ranked.map((surface) => surface.category),
            }});
          }}
        }}
        console.log(JSON.stringify({{
          stoneOption: stone.floor.surfaceOption,
          warmOakOption: warmOak.floor.surfaceOption,
          failures,
          wetSafetyFailures,
        }}));
        """
    )

    assert result["stoneOption"] == "stone_gray"
    # Step 9 keeps the remote bella StylePack unchanged; Step 6 applies its
    # warm-oak recommendation inside scene_design_materials.js only.
    assert result["warmOakOption"] == "stone_gray"
    assert result["failures"] == []
    assert result["wetSafetyFailures"] == []


def test_all_18_colorways_are_scored_for_every_floor04_room_and_surface_kind() -> None:
    module_uri = (STATIC / "scene_design_materials.js").as_uri()
    style_uri = (STATIC / "scene_style_packs.js").as_uri()
    catalog_uri = (ROOT / "backend" / "catalog" / "data" / "surface_catalog.json").as_uri()
    result = run_workflow_script(
        f"""
        import {{ readFileSync }} from "node:fs";
        import {{ fileURLToPath }} from "node:url";
        import {{
          groupStylePacks,
          rankSurfaceCatalog,
        }} from {json.dumps(module_uri)};
        import {{ STYLE_PACKS }} from {json.dumps(style_uri)};

        const catalog = JSON.parse(readFileSync(fileURLToPath({json.dumps(catalog_uri)}), "utf8"));
        const roomTypes = [
          "dormitory",
          "kitchen",
          "deposit",
          "circulation",
          "bathroom",
          "living_room",
          "balcony",
        ];
        const failures = [];
        for (const roomType of roomTypes) {{
          for (const usage of ["wall", "floor"]) {{
            for (const family of groupStylePacks(STYLE_PACKS)) {{
              for (const pack of family.packs) {{
                const ranked = rankSurfaceCatalog({{
                  surfaces: catalog.surfaces,
                  usage,
                  roomType,
                  styleId: pack.id,
                  stylePack: pack,
                  styleProfiles: catalog.style_surface_profiles,
                  limit: 6,
                }});
                const ids = ranked.map((surface) => surface.surface_id);
                const exactStyleLabel = `「${{pack.styleLabel}}・${{pack.name}}」`;
                if (
                  ids.length !== 6
                  || new Set(ids).size !== ids.length
                  || !ranked.every((surface) => (
                    surface.recommendationReason.includes(exactStyleLabel)
                  ))
                ) {{
                  failures.push({{
                    roomType,
                    usage,
                    pack: pack.id,
                    ids,
                    reasons: ranked.map((surface) => surface.recommendationReason),
                  }});
                }}
              }}
            }}
          }}
        }}
        console.log(JSON.stringify({{ failures }}));
        """
    )

    assert result["failures"] == []


def test_variant_tie_break_never_overrides_a_better_semantic_color_match() -> None:
    module_uri = (STATIC / "scene_design_materials.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ rankSurfaceCatalog }} from {json.dumps(module_uri)};

        const shared = {{
          category: "paint",
          material_group: "塗料",
          texture_url: "/paint.png",
          usage: ["wall"],
          suitable_styles: ["modern"],
        }};
        const ranked = rankSurfaceCatalog({{
          surfaces: [
            {{
              ...shared,
              surface_id: "exact-white",
              name_zh: "精準白",
              color_hex: "#ffffff",
            }},
            {{
              ...shared,
              surface_id: "near-white",
              name_zh: "近似白",
              color_hex: "#e8e8e8",
            }},
          ],
          usage: "wall",
          roomType: "living_room",
          styleId: "modern_minimal_1",
          stylePack: {{
            id: "modern_minimal_1",
            styleId: "modern_minimal",
            styleLabel: "現代簡約",
            name: "黑白俐落",
            wall: {{ color: "#ffffff", surfaceOption: "warm_white" }},
          }},
        }});
        console.log(JSON.stringify(ranked.map((surface) => surface.surface_id)));
        """
    )

    assert result[0] == "exact-white"


def test_style_colorway_change_preserves_existing_room_material_edits() -> None:
    module_uri = (STATIC / "scene_design_materials.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ applyStylePackPreference }} from {json.dumps(module_uri)};

        const preferences = {{
          styleId: "scandinavian_1",
          styleConfirmed: true,
          wholeHouse: {{
            wallSurfaceId: "wall-existing",
            floorSurfaceId: "floor-existing",
            wallColor: "#ffffff",
            floorColor: "#dddddd",
          }},
          rooms: {{
            bedroom: {{
              confirmed: false,
              surfaceOverride: {{
                wallSurfaceId: "wall-bedroom",
                floorSurfaceId: "floor-bedroom",
              }},
              materialBoundary: {{
                surface: "wall",
                secondarySurfaceId: "wall-accent",
                splitRatio: 0.4,
              }},
            }},
            storage: {{
              confirmed: false,
              surfaceOverride: {{
                wallSurfaceId: "wall-existing",
                floorSurfaceId: "floor-existing",
                wallColor: "#ffffff",
                floorColor: "#dddddd",
              }},
              materialBoundary: null,
            }},
            kitchen: {{
              confirmed: true,
              surfaceOverride: {{
                wallSurfaceId: "wall-existing",
                floorSurfaceId: "floor-existing",
                wallColor: "#ffffff",
                floorColor: "#dddddd",
              }},
              materialBoundary: null,
            }},
          }},
        }};
        const next = applyStylePackPreference({{
          preferences,
          stylePack: {{
            id: "industrial_2",
            wall: {{ color: "#444444" }},
            floor: {{ color: "#777777" }},
          }},
        }});
        console.log(JSON.stringify({{ preferences, next }}));
        """
    )

    assert result["next"]["styleId"] == "industrial_2"
    assert result["next"]["styleConfirmed"] is True
    assert result["next"]["wholeHouse"]["wallColor"] == "#444444"
    assert result["next"]["wholeHouse"]["floorColor"] == "#777777"
    assert result["next"]["wholeHouse"]["wallSurfaceId"] == "wall-existing"
    assert result["next"]["wholeHouse"]["floorSurfaceId"] == "floor-existing"
    assert (
        result["next"]["rooms"]["bedroom"]
        == result["preferences"]["rooms"]["bedroom"]
    )
    assert result["next"]["rooms"]["storage"]["surfaceOverride"] == {
        "wallSurfaceId": "wall-existing",
        "floorSurfaceId": "floor-existing",
        "wallColor": "#444444",
        "floorColor": "#777777",
    }
    assert (
        result["next"]["rooms"]["kitchen"]
        == result["preferences"]["rooms"]["kitchen"]
    )


def test_hand_drawn_material_line_becomes_renderer_compatible_boundary_json() -> None:
    module_uri = (STATIC / "scene_design_materials.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{
          applySurfaceSelectionToRooms,
          createMaterialBoundary,
          roomMaterialCompletion,
        }} from {json.dumps(module_uri)};

        const floor = createMaterialBoundary({{
          surface: "floor",
          start: {{ x: 0.35, y: 0.1 }},
          end: {{ x: 0.35, y: 0.9 }},
          primarySurfaceId: "oak",
          primaryColor: "#c9a77d",
          secondarySurfaceId: "tile",
          secondaryColor: "#d8d2c8",
        }});
        const wall = createMaterialBoundary({{
          surface: "wall",
          wallFace: "east",
          start: {{ x: 0.1, y: 0.62 }},
          end: {{ x: 0.9, y: 0.62 }},
          primarySurfaceId: "paint",
          primaryColor: "#f4efe4",
          secondarySurfaceId: "wood-panel",
          secondaryColor: "#8b684b",
        }});
        const floorHorizontal = createMaterialBoundary({{
          surface: "floor",
          start: {{ x: 0.1, y: 0.2 }},
          end: {{ x: 0.9, y: 0.2 }},
        }});
        const applied = applySurfaceSelectionToRooms({{
          preferences: {{
            wholeHouse: {{ wallSurfaceId: "old-wall", floorSurfaceId: "old-floor" }},
            rooms: {{
              bedroom: {{
                surfaceOverride: {{
                  wallSurfaceId: "bedroom-wall",
                  floorSurfaceId: "bedroom-floor",
                }},
              }},
              kitchen: {{
                surfaceOverride: {{
                  wallSurfaceId: "kitchen-wall",
                  floorSurfaceId: "kitchen-floor",
                }},
              }},
            }},
          }},
          roomIds: ["bedroom", "kitchen"],
          targetRoomId: "all",
          selection: {{
            wallSurfaceId: "new-wall",
            floorSurfaceId: "new-floor",
            wallColor: "#eeeeee",
            floorColor: "#bbbbbb",
          }},
        }});
        console.log(JSON.stringify({{
          floor,
          floorHorizontal,
          wall,
          applied,
          complete: roomMaterialCompletion({{
            surfaceOverride: {{
              wallSurfaceId: "paint",
              floorSurfaceId: "oak",
            }},
            confirmed: true,
          }}),
        }}));
        """
    )

    assert result["floor"]["surface"] == "floor"
    assert result["floor"]["direction"] == "vertical"
    assert result["floor"]["schemaVersion"] == "1.1"
    assert result["floor"]["coordinateSpace"] == "room-relative-ratio"
    assert result["floor"]["coordinateUnit"] == "ratio"
    assert result["floor"]["splitRatio"] == 0.35
    assert "points" not in result["floor"]
    assert result["floorHorizontal"]["direction"] == "horizontal"
    assert result["floorHorizontal"]["splitRatio"] == 0.8
    assert result["wall"]["surface"] == "wall"
    assert result["wall"]["wallFace"] == "east"
    assert result["wall"]["direction"] == "horizontal"
    assert result["wall"]["splitRatio"] == 0.38
    assert result["wall"]["secondarySurfaceId"] == "wood-panel"
    assert result["applied"]["wholeHouse"]["wallSurfaceId"] == "new-wall"
    assert result["applied"]["rooms"]["bedroom"]["surfaceOverride"]["wallSurfaceId"] == "new-wall"
    assert result["applied"]["rooms"]["kitchen"]["surfaceOverride"]["floorSurfaceId"] == "new-floor"
    assert result["complete"]["complete"] is True


def test_step_six_material_ui_is_visual_room_based_and_drawable() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    for expected in (
        'id="design-style-variant-grid"',
        'id="design-room-plan-stage"',
        'id="design-room-plan-image"',
        'id="design-room-plan-overlay"',
        'id="design-room-progress"',
        'id="design-room-nav"',
        'id="design-material-tabs"',
        'id="design-material-card-grid"',
        'id="design-material-recommendation"',
        'id="design-material-pagination"',
        'id="previous-design-material-page"',
        'id="design-material-page-status"',
        'id="design-material-page-numbers"',
        'id="next-design-material-page"',
        'id="design-material-target"',
        'id="design-cut-editor"',
        'id="design-cut-canvas"',
        'tabindex="0"',
        'id="design-cut-keyboard-hint"',
        'id="design-cut-wall-face"',
        'id="confirm-design-room"',
    ):
        assert expected in html

    for expected in (
        "renderDesignStyleCards",
        "renderDesignRoomLocator",
        "renderDesignMaterialCards",
        "renderDesignMaterialPagination",
        "renderDesignCutEditor",
        "handleDesignCutPointerDown",
        "handleDesignCutPointerUp",
        "handleDesignCutKeyDown",
        "createMaterialBoundary(",
        "paginateSurfaceCatalog(",
        "roomMaterialCompletion(",
        'button.tabIndex = active ? 0 : -1;',
        'element.designMaterialTabs.addEventListener("keydown"',
        '"ArrowLeft"',
        '"ArrowRight"',
        '"Home"',
        '"End"',
    ):
        assert expected in controller

    assert 'id="design-material-page-status" aria-live="polite"' in html
    assert 'id="previous-design-material-page" type="button"' in html
    assert 'id="next-design-material-page" type="button"' in html

    assert 'class="rp-legacy-material-controls" hidden aria-hidden="true"' in html
    assert html.index('class="rp-legacy-material-controls" hidden aria-hidden="true"') < html.index(
        'id="room-material-cuts"'
    )
    assert 'id="room-wall-preference" multiple' not in html
    assert 'id="room-floor-preference" multiple' not in html
    assert 'invalidateDownstreamFrom(\n    "design_preferences"' in controller

    material_cards = controller[
        controller.index("function renderDesignMaterialCards("):
        controller.index("function materialBoundaryDisplayPoint(")
    ]
    assert "selectedSurfaceEligible = isSurfaceEligibleForRoom(" in material_cards
    assert "&& selectedSurfaceEligible" in material_cards
    assert "需重新選擇：" in material_cards

    confirmation = controller[
        controller.index("function confirmActiveDesignRoom("):
        controller.index("function applyActiveDesignRoomToUnconfirmed(")
    ]
    assert "designRoomMaterialCompletion(room" in confirmation
    assert 'item.includes("ineligible")' in confirmation

    select_room = controller[
        controller.index("function selectDesignRoom("):
        controller.index("async function renderDesignPreferences(")
    ]
    apply_style = controller[
        controller.index("function applyDesignStylePack("):
        controller.index("function renderDesignBaselineSummary(")
    ]
    assert 'state.activeDesignMaterialTarget = "primary";' in select_room
    assert 'state.activeDesignMaterialTarget = "primary";' in apply_style
    assert controller.count("invalidateGeneratedSchemesAfterDesignChange();") >= 8
    assert "room_polygon_cm: boundaryRoom.polygon_cm.map" in controller


def test_step_seven_workbench_filters_and_guards_material_mutations() -> None:
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    render_controls = controller[
        controller.index("function renderWorkbenchMaterialControls("):
        controller.index("async function ensureDesignAssets(")
    ]
    assert "activeRoom?.type" in render_controls
    assert render_controls.count("renderSurfaceSelect(") == 3

    apply_materials = controller[
        controller.index("function applyWorkbenchMaterials("):
        controller.index("function updateWorkbenchMaterialBoundary(")
    ]
    assert "validateSurfaceSelectionForRooms({" in apply_materials
    assert "if (!validation.valid)" in apply_materials
    assert apply_materials.index("if (!validation.valid)") < apply_materials.index(
        "applySurfaceSelectionToRooms({"
    )

    update_boundary = controller[
        controller.index("function updateWorkbenchMaterialBoundary("):
        controller.index("function renderLayoutRoomFilter(")
    ]
    assert "validateSurfaceSelectionForRooms({" in update_boundary
    assert "isSurfaceEligibleForRoom(secondarySurface" in update_boundary
    assert update_boundary.index("if (!primaryValidation.valid)") < update_boundary.index(
        "nextRoomPreferences.materialBoundary = createMaterialBoundary({"
    )
