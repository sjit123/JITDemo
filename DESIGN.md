---
version: alpha
name: High-Fidelity Security Operations System
description: A dark, glassmorphism-forward interface for high-stakes just-in-time access workflows.
colors:
  surface: "#0B1326"
  surface-dim: "#0B1326"
  surface-bright: "#31394D"
  surface-container-lowest: "#060E20"
  surface-container-low: "#131B2E"
  surface-container: "#171F33"
  surface-container-high: "#222A3D"
  surface-container-highest: "#2D3449"
  on-surface: "#DAE2FD"
  on-surface-variant: "#C1C6D7"
  inverse-surface: "#DAE2FD"
  inverse-on-surface: "#283044"
  outline: "#8B90A0"
  outline-variant: "#414755"
  surface-tint: "#ADC6FF"
  primary: "#ADC6FF"
  on-primary: "#002E69"
  primary-container: "#4B8EFF"
  on-primary-container: "#00285C"
  inverse-primary: "#005BC1"
  secondary: "#4EDEA3"
  on-secondary: "#003824"
  secondary-container: "#00A572"
  on-secondary-container: "#00311F"
  tertiary: "#C0C1FF"
  on-tertiary: "#1000A9"
  tertiary-container: "#8083FF"
  on-tertiary-container: "#0D0096"
  error: "#FFB4AB"
  on-error: "#690005"
  error-container: "#93000A"
  on-error-container: "#FFDAD6"
  primary-fixed: "#D8E2FF"
  primary-fixed-dim: "#ADC6FF"
  on-primary-fixed: "#001A41"
  on-primary-fixed-variant: "#004493"
  secondary-fixed: "#6FFBBE"
  secondary-fixed-dim: "#4EDEA3"
  on-secondary-fixed: "#002113"
  on-secondary-fixed-variant: "#005236"
  tertiary-fixed: "#E1E0FF"
  tertiary-fixed-dim: "#C0C1FF"
  on-tertiary-fixed: "#07006C"
  on-tertiary-fixed-variant: "#2F2EBE"
  background: "#0B1326"
  on-background: "#DAE2FD"
  surface-variant: "#2D3449"
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: 700
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: 600
    lineHeight: 32px
    letterSpacing: -0.01em
  body-base:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: 400
    lineHeight: 24px
    letterSpacing: 0em
  label-caps:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: 600
    lineHeight: 16px
    letterSpacing: 0.05em
  mono-data:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: 500
    lineHeight: 20px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base-unit: 4px
  gutter: 24px
  margin-desktop: 40px
  margin-mobile: 16px
  container-max: 1440px
components:
  app-shell:
    backgroundColor: "{colors.background}"
    textColor: "{colors.on-background}"
    typography: "{typography.body-base}"
  sidebar-nav:
    backgroundColor: "{colors.surface-container-low}"
    textColor: "{colors.on-surface}"
    rounded: "{rounded.md}"
  sidebar-nav-active:
    backgroundColor: "{colors.primary-container}"
    textColor: "{colors.on-primary-container}"
    rounded: "{rounded.md}"
  panel-glass:
    backgroundColor: "{colors.surface-container}"
    textColor: "{colors.on-surface}"
    rounded: "{rounded.lg}"
    padding: 16px
  button-primary:
    backgroundColor: "{colors.primary-container}"
    textColor: "{colors.on-primary-container}"
    typography: "{typography.label-caps}"
    rounded: "{rounded.md}"
    height: 40px
    padding: 0 16px
  button-primary-hover:
    backgroundColor: "{colors.inverse-primary}"
  alert-success:
    backgroundColor: "{colors.secondary-container}"
    textColor: "{colors.on-secondary-container}"
    rounded: "{rounded.md}"
    padding: 12px
  alert-error:
    backgroundColor: "{colors.error-container}"
    textColor: "{colors.on-error-container}"
    rounded: "{rounded.md}"
    padding: 12px
  alert-info:
    backgroundColor: "{colors.surface-container-high}"
    textColor: "{colors.on-surface}"
    rounded: "{rounded.md}"
    padding: 12px
  tab-active:
    backgroundColor: "{colors.primary-container}"
    textColor: "{colors.on-primary-container}"
    rounded: "{rounded.md}"
  audit-row-success:
    backgroundColor: "{colors.on-secondary-fixed}"
    textColor: "{colors.on-surface}"
  audit-row-denied:
    backgroundColor: "{colors.on-error}"
    textColor: "{colors.on-surface}"
  audit-row-expired:
    backgroundColor: "{colors.surface-container-high}"
    textColor: "{colors.on-surface}"
---

## Overview

This system is designed for security operations where confidence and legibility are more important than decoration. It uses a command-center visual language: dark layered surfaces, high-contrast data, and tight emphasis on status and task flow.

The interface should feel calm and technical. Visual hierarchy is created through tone, spacing, and typography instead of heavy ornamentation.

## Colors

The palette is anchored in deep midnight blues and slate surfaces, with electric blue as the action color and emerald for positive authorization states.

- Primary blue communicates active workflow and intentional action.
- Emerald indicates successful, healthy, and permitted states.
- Red tones indicate denial, failures, and urgent security exceptions.
- Layered dark surfaces preserve focus during long operations and reduce visual fatigue.

## Typography

Typography is data-first and operational:

- Inter is the primary reading and interface family.
- Geist labels are compact and explicit for controls and small metadata.
- JetBrains Mono is used for credential-like and audit-style payload text.
- Headline and body weights are separated clearly to make scan-order obvious.

## Layout & Spacing

The layout model is a fluid wide canvas with explicit operational zones:

- Left sidebar remains persistent for tool switching and context continuity.
- Main canvas prioritizes workflows, events, and active leases.
- Spacing follows a 4px rhythm for precise alignment of dense controls.
- Containers should keep generous desktop margins and tighter mobile margins.

## Elevation & Depth

Depth is communicated through layered translucent surfaces rather than strong drop shadows.

- Base layer uses deepest background tones.
- Surface layer uses subtle tint differences and fine outlines.
- Active layer receives a restrained blue glow to signal focus.
- Shadows, where used, stay soft and low-opacity.

## Shapes

Shape language is precise but not sharp:

- Most controls use medium radii for a technical but approachable feel.
- Cards and interactive rows share rounded geometry for consistency.
- Circular affordances are reserved for status and time-bound indicators.

## Components

Core component behavior:

- Primary buttons are electric-blue with high contrast text.
- Panels should read as glass layers with subtle borders.
- Tabs and selected navigation states should visibly anchor active context.
- Alerts and audit rows use semantic tones that are readable on dark surfaces.
- Monospace text should appear in code blocks, tokens, and machine-like details.

## Do's and Don'ts

- Do maintain semantic state colors for success, denial, and neutral operational context.
- Do keep layered dark surfaces and subtle outlines consistent.
- Do preserve high readability for data tables and logs.
- Do use glow effects sparingly for active focus only.
- Don't introduce bright non-semantic accent colors.
- Don't flatten all surfaces into a single tone.
- Don't overuse heavy shadows that muddy the dark interface.
- Don't style alerts and statuses without semantic meaning.
