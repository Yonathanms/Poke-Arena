/**
 * Loader de pruebas para Node.js (`node --experimental-strip-types --import ./tests/ts-tsx-loader.mjs --test`).
 *
 * Permite al test runner nativo de Node:
 * 1. Resolver importaciones internas de Vite sin extensión (`.ts` / `.tsx`) o con alias `@/`.
 * 2. Transpilar archivos `.tsx` en memoria usando el compilador oficial de `typescript` ya
 *    instalado en `frontend/node_modules`, sin añadir dependencias externas al proyecto.
 */

import fs from "node:fs/promises";
import { register } from "node:module";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import ts from "typescript";

const FRONTEND_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SRC_ROOT = path.join(FRONTEND_ROOT, "src");

async function fileExists(filePath) {
  try {
    const stat = await fs.stat(filePath);
    return stat.isFile();
  } catch {
    return false;
  }
}

async function resolveCandidatePath(basePath) {
  const candidates = [
    basePath,
    `${basePath}.ts`,
    `${basePath}.tsx`,
    path.join(basePath, "index.ts"),
    path.join(basePath, "index.tsx"),
  ];
  for (const candidate of candidates) {
    if (await fileExists(candidate)) {
      return pathToFileURL(candidate).href;
    }
  }
  return null;
}

export async function resolve(specifier, context, nextResolve) {
  if (specifier.startsWith("@/")) {
    const targetBase = path.join(SRC_ROOT, specifier.slice(2));
    const resolvedUrl = await resolveCandidatePath(targetBase);
    if (resolvedUrl) {
      return { url: resolvedUrl, shortCircuit: true };
    }
  }

  if (
    (specifier.startsWith("./") || specifier.startsWith("../")) &&
    context.parentURL &&
    context.parentURL.startsWith("file:")
  ) {
    const parentDir = path.dirname(fileURLToPath(context.parentURL));
    const targetBase = path.resolve(parentDir, specifier);
    const resolvedUrl = await resolveCandidatePath(targetBase);
    if (resolvedUrl) {
      return { url: resolvedUrl, shortCircuit: true };
    }
  }

  return nextResolve(specifier, context);
}

export async function load(url, context, nextLoad) {
  if (url.startsWith("file:") && (url.endsWith(".tsx") || url.endsWith(".ts"))) {
    const filePath = fileURLToPath(url);
    const sourceText = await fs.readFile(filePath, "utf8");
    const transpiled = ts.transpileModule(sourceText, {
      fileName: filePath,
      compilerOptions: {
        target: ts.ScriptTarget.ES2022,
        module: ts.ModuleKind.ESNext,
        jsx: ts.JsxEmit.ReactJSX,
        sourceMap: false,
      },
    });
    return {
      format: "module",
      source: transpiled.outputText,
      shortCircuit: true,
    };
  }
  return nextLoad(url, context);
}

// Si se carga vía `--import`, se auto-registra como hook de módulos ESM
if (! import.meta.url.includes("?registered")) {
  register(`${import.meta.url}?registered`, pathToFileURL("./"));
}
