---
name: Academic Precision
colors:
  surface: '#f8f9fa'
  surface-dim: '#d9dadb'
  surface-bright: '#f8f9fa'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f4f5'
  surface-container: '#edeeef'
  surface-container-high: '#e7e8e9'
  surface-container-highest: '#e1e3e4'
  on-surface: '#191c1d'
  on-surface-variant: '#43474f'
  inverse-surface: '#2e3132'
  inverse-on-surface: '#f0f1f2'
  outline: '#747780'
  outline-variant: '#c4c6d0'
  surface-tint: '#405f90'
  primary: '#0f3463'
  on-primary: '#ffffff'
  primary-container: '#2b4b7b'
  on-primary-container: '#9dbcf3'
  inverse-primary: '#a9c7ff'
  secondary: '#5b5f62'
  on-secondary: '#ffffff'
  secondary-container: '#dde0e3'
  on-secondary-container: '#5f6366'
  tertiary: '#2d353c'
  on-tertiary: '#ffffff'
  tertiary-container: '#434c53'
  on-tertiary-container: '#b3bcc5'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d6e3ff'
  primary-fixed-dim: '#a9c7ff'
  on-primary-fixed: '#001b3d'
  on-primary-fixed-variant: '#264777'
  secondary-fixed: '#e0e3e6'
  secondary-fixed-dim: '#c4c7ca'
  on-secondary-fixed: '#181c1e'
  on-secondary-fixed-variant: '#43474a'
  tertiary-fixed: '#dbe4ed'
  tertiary-fixed-dim: '#bfc8d0'
  on-tertiary-fixed: '#141d23'
  on-tertiary-fixed-variant: '#3f484f'
  background: '#f8f9fa'
  on-background: '#191c1d'
  surface-variant: '#e1e3e4'
typography:
  h1:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  h2:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.3'
    letterSpacing: -0.01em
  h3:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: '1.4'
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.6'
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.5'
  label-caps:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '700'
    lineHeight: '1'
    letterSpacing: 0.05em
  button:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: '1'
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 8px
  container-max: 1140px
  gutter: 24px
  section-gap: 48px
  element-gap: 16px
---

## Brand & Style

This design system is built for an academic research environment where clarity, objectivity, and focus are paramount. The brand personality is institutional yet modern, conveying the reliability of the University of Mannheim while maintaining the efficiency of a high-tech experimental tool.

The visual style follows a **Corporate / Modern** approach with heavy influences from **Minimalism**. It prioritizes high legibility and clear information hierarchy to reduce cognitive load during complex setup tasks. The UI avoids unnecessary decorative elements, instead using structured containers and purposeful white space to guide the researcher through the experimental workflow.

## Colors

The palette is anchored by a deep institutional blue, serving as the primary color for brand identity and high-priority actions. 

- **Primary:** Used for main buttons, active states, and navigational accents.
- **Surface & Backgrounds:** A clean white base is used for the primary canvas, while a light gray (`#F8F9FA`) defines secondary sections or grouped content areas.
- **Borders & Dividers:** Subtle gray borders (`#DEE2E6`) provide structure without creating visual noise.
- **Status Indicators:** Success, Error, and Warning colors should be used sparingly but distinctly to indicate data validity and system feedback.

## Typography

The design system utilizes **Inter** as its sole typeface. Chosen for its exceptional legibility in digital interfaces and technical environments, Inter provides the necessary "utilitarian" feel for a research platform.

Headlines are set with tight letter-spacing and heavy weights to provide clear section entry points. Body copy maintains a generous line height to ensure readability of long-form descriptions. Small labels and metadata use a bold, uppercase style to differentiate them from interactive content.

## Layout & Spacing

This design system employs a **Fixed Grid** philosophy for centralized data management, centering the content within a maximum width to ensure readability on wide academic monitors.

- **Grid:** A 12-column grid system is used for layout structure.
- **Rhythm:** An 8px base unit governs all padding and margins, ensuring a consistent vertical rhythm.
- **Sectioning:** Large gaps (48px) separate major logical groups (e.g., "Experiment Name" vs "Datasets"), while smaller gaps (16px) are used for internal component spacing.

## Elevation & Depth

To maintain a clean, experimental aesthetic, this design system avoids heavy drop shadows. Depth is communicated primarily through **Tonal Layers** and **Low-contrast outlines**.

- **Level 0 (Base):** The main white background.
- **Level 1 (Sections):** Light gray background fills (`#F8F9FA`) or thin borders (`#DEE2E6`) are used to group related fields.
- **Level 2 (Interactive):** Elements like dropdown menus or active cards may use a very subtle, diffused ambient shadow (0px 4px 12px, 5% opacity) to indicate they are floating above the layout.

## Shapes

The shape language is **Soft**, utilizing small radii to take the edge off the technical interface without appearing too consumer-oriented. 

- Standard components (Inputs, Buttons) use a 0.25rem (4px) radius.
- Container blocks and larger cards use a 0.5rem (8px) radius to softly frame content sections.

## Components

### Buttons
Primary buttons use the dark blue background with white text. Secondary buttons use a light gray background or an outline style. "Next" and "Upload" actions should include subtle icons (chevron-right, upload) to enhance affordance.

### Input Fields
Inputs are defined by a 1px border. The placeholder text uses a light gray, which vanishes upon focus. On focus, the border should transition to the primary blue with a subtle outer glow to indicate activity.

### File Upload Indicators
Upload areas should be distinct containers. Once a file is uploaded, a "Status Table" or list view must appear, showing the filename, file size, and a status indicator (dot or tag) indicating "Active" or "Processing."

### Section Headers
Headers must be prominent. Use H2 for major categories and H3 for sub-settings. Every section should be preceded by a clear, bold title to ensure the user always knows their current stage in the setup process.

### Cards & Selection
For selecting "Design Types," use large selectable cards. These cards should have a subtle border that thickens and changes to the primary color when selected, accompanied by a checkmark icon.