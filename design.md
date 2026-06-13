# Design System: Industrial Workbench Schematic

## 1. Definição do Estilo

- **Nome:** Industrial Workbench Schematic
- **Tipo:** Rugged, Industrial, Hardware
- **Keywords:** industrial, workbench, garage, metal, tools, grunge, workshop, hardware, reliable
- **Era:** Classic Industrial
- **Light/Dark:** ✓ Full / ✗ No

## 2. Paleta de Cores

- **Primárias:** Background #cfd3d6, Text #1f1f1f, Accent #ffc107
- **Secundárias:** Rust #8B4513, Steel #71797E, Rubber Black #2B2B2B, Caution Yellow #FFD700

## 3. Efeitos Visuais

Brushed aluminum textures, scratches, metallic plaques, workshop tool borders, realistic soft drop shadows.

## 4. AI Prompt Keywords

industrial workbench landing, garage style, workshop aesthetic, metal textures, tools background, rugger design, hardware focus.

## 5. CSS Technical

```css
background-color: #cfd3d6; color: #1f1f1f; font-family: 'Roboto Condensed', sans-serif; background-image: url('https://www.transparenttextures.com/patterns/brushed-alum.png'); border: 4px solid #444; border-radius: 4px;
```

## 6. Design System Variables

```css
--metal-grey: #cfd3d6, --tool-black: #1f1f1f, --caution-yellow: #ffc107, --rust-accent: #8B4513, --shadow-hard: 2px 2px 0px #000
```

## 7. Checklist de Implementação

- ☐ Metallic/Concrete textures
- ☐ Warning stripes/colors
- ☐ Bold condensed typography
- ☐ Tool-like interactive elements
- ☐ Shadows simulating depth/screws

## 8. Visual Theme & Atmosphere

Industrial Workbench Schematic — Design technical com industrial, workbench, garage. Template e prompt pronto para IA. Estilo Industrial Workbench Schematic representa uma tendência moderna em design UI/UX web com foco em technical.

- Density: 5/10 — Balanced
- Variance: 8/10 — Expressive
- Motion: 4/10 — Subtle

## 9. Color Palette & Roles

- **Background** (#cfd3d6) — Primary background surface
- **Text** (#1f1f1f) — Primary text color
- **Accent** (#ffc107) — Primary accent, CTAs and interactive elements
- **Rust** (#8B4513) — Extended palette, decorative use
- **Steel** (#71797E) — Extended palette, decorative use
- **Rubber Black** (#2B2B2B) — Deep contrast surface
- **Caution Yellow** (#FFD700) — Warning states, attention indicators

## 10. Typography Rules

- **Display / Hero:** Roboto Condensed — Weight 700, tight tracking, used for headline impact
- **Body:** Roboto Condensed — Weight 400, 16px/1.6 line-height, max 72ch per line
- **UI Labels / Captions:** Roboto Condensed — 0.875rem, weight 500, slight letter-spacing
- **Monospace:** JetBrains Mono — Used for code, metadata, and technical values

Scale:
- Hero: clamp(2.5rem, 5vw, 4rem)
- H1: 2.25rem
- H2: 1.5rem
- Body: 1rem / 1.6
- Small: 0.875rem

## 11. Component Stylings

- **Primary Button:** Rounded (4px) shape. Accent color fill. Hover: 8% darken + subtle lift shadow. Active: -1px translate tactile press. Font weight 600. No outer glows.
- **Secondary / Ghost Button:** Outline variant. 1.5px border in muted color. Text in primary color. Hover: subtle background fill.
- **Cards:** Rounded (4px) corners. Surface background. Subtle shadow (0 2px 12px rgba(0,0,0,0.06)). 1px border stroke.
- **Inputs:** Label above input. 1px border stroke. Focus ring: 2px accent color offset 2px. Error text below in semantic red. No floating labels.
- **Navigation:** Primary surface background. Active item: accent color indicator. Font weight 500 when active.
- **Skeletons:** Shimmer animation matching component dimensions. No circular spinners.
- **Empty States:** Icon-based composition with descriptive text and action button.

## 12. Layout Principles

- **Grid:** CSS Grid primary. Max-width containment: 1280px centered with 1.5rem side padding.
- **Spacing rhythm:** Balanced. Base unit: 0.5rem (8px).
- **Section vertical gaps:** clamp(4rem, 8vw, 8rem).
- **Hero layout:** Asymmetric composition.
- **Feature sections:** Asymmetric grid with varied card sizes. No 3-equal-columns.
- **Mobile collapse:** All multi-column layouts collapse below 768px. No horizontal overflow.
- **z-index contract:** base (0) / sticky-nav (100) / overlay (200) / modal (300) / toast (500).

## 13. Motion & Interaction

- **Physics:** Ease-out curves, 200-300ms duration. Smooth and predictable.
- **Entry animations:** Fade + translate-Y (16px → 0) over 420ms ease-out. Staggered cascades for lists: 80ms between items.
- **Hover states:** Subtle color shift + shadow adjustment over 200ms.
- **Page transitions:** Fade only (200ms).
- **Performance:** Only transform and opacity animated. No layout-triggering properties.

## 14. Anti-Patterns (Banned)

- No emojis in UI — use icon system only (Lucide, Heroicons)
- No pure black (#000000) — use off-black or charcoal variants
- No oversaturated accent colors (saturation cap: 80%)
- No 3-column equal-width feature layouts — use zig-zag or asymmetric grid
- No `h-screen` — use `min-h-[100dvh]`
- No AI copywriting clichés: "Elevate", "Seamless", "Unleash", "Next-Gen"
- No broken external image links — use picsum.photos or inline SVG
- No generic lorem ipsum in demos

## Contexto Histórico

Estilo Industrial Workbench Schematic representa uma tendência moderna em design UI/UX web com foco em technical.

## Caso de Uso

Landing pages, Websites modernas
