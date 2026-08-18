// PostCSS config for the CAO MCP App views (Mantine 9.5.1).
// postcss-preset-mantine processes Mantine's CSS; postcss-simple-vars provides
// the standard breakpoint variables Mantine's CSS references.
export default {
  plugins: {
    "postcss-preset-mantine": {},
    "postcss-simple-vars": {
      variables: {
        "mantine-breakpoint-xs": "36em",
        "mantine-breakpoint-sm": "48em",
        "mantine-breakpoint-md": "62em",
        "mantine-breakpoint-lg": "75em",
        "mantine-breakpoint-xl": "88em",
      },
    },
  },
};
