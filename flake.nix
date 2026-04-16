{
  description = "Entorno ETL - Datos Urbanos MVD";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }: {
    devShells.x86_64-linux.default =
      let pkgs = nixpkgs.legacyPackages.x86_64-linux;
      in pkgs.mkShell {
        packages = with pkgs; [
          opencode
          (pkgs.python3.withPackages (ps: with ps; [
            pandas
            geopandas
            requests
            pyarrow 
            jupyter
            tqdm
            polars
            pip

            pyproj
          ]))
        ];
      };
  };
}
