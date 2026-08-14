import { useEffect, useState } from "react";

interface ITokenRow {
  name: string;
  value: string;
}

interface ITokenGroup {
  title: string;
  tokens: string[];
  swatch?: boolean;
}

const GROUPS: ITokenGroup[] = [
  { title: "Surface", tokens: ["--bg", "--bg-tertiary", "--bg-subtle", "--bg-hover", "--bg-input"], swatch: true },
  { title: "Border", tokens: ["--border", "--border-strong", "--border-focus"], swatch: true },
  { title: "Ink", tokens: ["--ink-1", "--ink-2", "--ink-3", "--ink-4"], swatch: true },
  {
    title: "Semantic",
    tokens: [
      "--green-500", "--green-600", "--red-500", "--red-600",
      "--blue-500", "--blue-600", "--amber-500", "--gray-500",
    ],
    swatch: true,
  },
  { title: "Accent", tokens: ["--accent", "--accent-600", "--accent-50"], swatch: true },
  { title: "Typography scale", tokens: ["--fs-hero", "--fs-lg", "--fs-base", "--fs-sm"] },
  { title: "Spacing scale", tokens: ["--space-1", "--space-2", "--space-3", "--space-4", "--space-5", "--space-6", "--space-7", "--space-8"] },
  { title: "Motion", tokens: ["--motion-fast", "--motion-base", "--motion-slow", "--ease-out"] },
  { title: "Radii", tokens: ["--r-sm", "--r-md", "--r-lg", "--r-xl"] },
];

function readTokens(names: string[]): ITokenRow[] {
  const styles = getComputedStyle(document.documentElement);
  return names.map((name) => ({ name, value: styles.getPropertyValue(name).trim() }));
}

export const Foundations = () => {
  const [groups, setGroups] = useState<{ title: string; swatch?: boolean; rows: ITokenRow[] }[]>([]);

  useEffect(() => {
    setGroups(GROUPS.map((g) => ({ title: g.title, swatch: g.swatch, rows: readTokens(g.tokens) })));
  }, []);

  return (
    <div style={{ fontFamily: "var(--font)", color: "var(--ink-1)" }}>
      <p style={{ color: "var(--ink-3)", marginBottom: 24 }}>
        Live values read from the current theme&apos;s computed CSS custom properties (toggle the
        Theme control in the toolbar above to see dark-mode values).
      </p>
      {groups.map((group) => (
        <section key={group.title} style={{ marginBottom: 32 }}>
          <h3 style={{ marginBottom: 12 }}>{group.title}</h3>
          <table style={{ borderCollapse: "collapse", width: "100%" }}>
            <tbody>
              {group.rows.map((row) => (
                <tr key={row.name} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td style={{ padding: "8px 12px", fontFamily: "var(--font-mono)", fontSize: 12 }}>
                    {row.name}
                  </td>
                  <td style={{ padding: "8px 12px", fontFamily: "var(--font-mono)", fontSize: 12 }}>
                    {row.value}
                  </td>
                  {group.swatch && (
                    <td style={{ padding: "8px 12px" }}>
                      <div
                        style={{
                          width: 24,
                          height: 24,
                          borderRadius: 4,
                          border: "1px solid var(--border-strong)",
                          background: row.value,
                        }}
                      />
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}
    </div>
  );
};
