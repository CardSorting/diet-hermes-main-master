# nix/tui.nix — Herm TUI (OpenTUI/Bun) prebuilt dist for HERMES_TUI_DIR
{ pkgs, ... }:
let
  src = ../herm-tui;
  packageJson = builtins.fromJSON (builtins.readFile (src + "/package.json"));
  version = packageJson.version;
in
pkgs.stdenv.mkDerivation {
  pname = "hermes-tui";
  inherit version src;

  nativeBuildInputs = [ pkgs.bun ];
  dontConfigure = true;

  buildPhase = ''
    runHook preBuild
    cd $sourceRoot
    bun install --frozen-lockfile
    bun run build
    runHook postBuild
  '';

  installPhase = ''
    runHook preInstall
    mkdir -p $out/lib/hermes-tui
    cp -r dist $out/lib/hermes-tui/dist
    cp package.json $out/lib/hermes-tui/
    runHook postInstall
  '';
}
