# nix/homeManagerModules.nix — the Home Manager module for prometheus-agent
#
# This module is the user-level equivalent of nixosModules.default. Prometheus is
# an agent for one person. The credentials, the memory, the sessions and the
# cron jobs all belong to that person. Thus a user-level module is correct on
# each distribution, and not only on NixOS.
#
# `services.prometheus-agent` is the same option set on both modules. All of the
# options except the system-level ones come from nix/moduleCommon.nix, so an
# example from the NixOS documentation works here without a change. Only the
# necessary parts are different:
#
#   removed   user, group, createUser  — Home Manager runs as the user
#   removed   container.*              — it needs root and the Docker socket
#   removed   UMask 0007               — that mode shares state with a UNIX
#                                        group, but this state has one user
#   changed   systemd.services         -> systemd.user.services or
#                                        launchd.agents
#   changed   system.activationScripts -> home.activation
#   changed   addToSystemPackages      -> installPackage and
#                                        home.sessionVariables
#   changed   stateDir (+ "/.prometheus")  -> prometheusHome, set directly
#
# To use the module:
#   imports = [ prometheus-agent.homeManagerModules.default ];
#   services.prometheus-agent = {
#     enable = true;
#     gateway.enable = true;
#     settings.model.default = "anthropic/claude-sonnet-4";
#     environmentFiles = [ config.sops.secrets."prometheus/env".path ];
#   };
#
# CAUTION: Enable linger for the account. Without linger, systemd stops the
# user manager at logout, and both units stop with it. Home Manager cannot
# run `loginctl enable-linger`. On NixOS, set
#   users.users.<name>.linger = true;
# On other systems, run `loginctl enable-linger <name>` one time.
{ inputs, ... }:
{
  flake.homeManagerModules.default =
    {
      config,
      lib,
      options,
      pkgs,
      ...
    }:

    let
      cfg = config.services.prometheus-agent;
      common = import ./moduleCommon.nix { inherit lib; };

      effectivePackage = common.effectivePackage cfg;
      prometheus-agent = inputs.self.packages.${pkgs.stdenv.hostPlatform.system}.default;

      inherit (pkgs.stdenv.hostPlatform) isDarwin isLinux;

      processEnvironment = common.processEnvironment {
        inherit (cfg) prometheusHome;
        # The CLI reads this value and names it when it refuses a
        # configuration change.
        managedSystem = "home-manager";
      };
      unitPath = lib.makeBinPath (common.processPath { inherit pkgs cfg; });

      # The systemd unit that the gateway and the backend both start from.
      mkUnit =
        {
          description,
          argv,
        }:
        {
          Unit = {
            Description = description;
            # Do not use network-online.target here. That is a system target.
            # A user unit that orders against it has no effect, and systemd
            # gives no message.
            After = [ "default.target" ];
          };
          Install.WantedBy = [ "default.target" ];
          Service = {
            Type = "simple";
            Environment = (lib.mapAttrsToList (k: v: "${k}=${v}") processEnvironment) ++ [
              "PATH=${unitPath}"
            ];
            ExecStart = lib.escapeShellArgs argv;
            WorkingDirectory = cfg.workingDirectory;
            Restart = cfg.restart;
            RestartSec = cfg.restartSec;
            # This state has one user. Keep it private. The NixOS module uses
            # 0007 to share the state with a UNIX group.
            UMask = "0077";
            NoNewPrivileges = true;
            PrivateTmp = true;
          };
        };

      mkAgent =
        { argv, logName }:
        {
          enable = true;
          config = {
            Label = "org.nix-community.home.${logName}";
            ProgramArguments = argv;
            EnvironmentVariables = processEnvironment // {
              PATH = "${unitPath}:/usr/bin:/bin:/usr/sbin:/sbin";
            };
            WorkingDirectory = cfg.workingDirectory;
            RunAtLoad = true;
            KeepAlive =
              if cfg.restart == "always" then
                true
              else
                {
                  SuccessfulExit = false;
                  Crashed = true;
                };
            ThrottleInterval = cfg.restartSec;
            StandardOutPath = "${config.home.homeDirectory}/Library/Logs/${logName}.log";
            StandardErrorPath = "${config.home.homeDirectory}/Library/Logs/${logName}.err.log";
            ProcessType = "Background";
          };
        };

    in
    {
      options.services.prometheus-agent =
        common.sharedOptions {
          defaultPackage = prometheus-agent;
          defaultPackageText = lib.literalExpression "prometheus-agent.packages.\${system}.default";
          defaultWorkingDirectory = config.home.homeDirectory;
          defaultWorkingDirectoryText = lib.literalExpression "config.home.homeDirectory";
        }
        // {
          prometheusHome = lib.mkOption {
            type = lib.types.str;
            default = "${config.home.homeDirectory}/.prometheus";
            defaultText = lib.literalExpression ''"''${config.home.homeDirectory}/.prometheus"'';
            description = ''
              The value of PROMETHEUS_HOME. This state directory holds
              config.yaml, .env, auth.json, the sessions, the skills, the
              memory and the cron jobs.

              The NixOS module takes a `stateDir` and adds `/.prometheus` to it.
              This module sets PROMETHEUS_HOME directly. Thus an existing
              ~/.prometheus continues to work, and you can give the directory any
              name.
            '';
            example = "/home/alice/.prometheus-work";
          };

          installPackage = lib.mkOption {
            type = lib.types.bool;
            default = true;
            description = ''
              Add the prometheus CLI to home.packages, and export PROMETHEUS_HOME
              with home.sessionVariables. Interactive shells then use the
              same state as the services.

              The equivalent NixOS option, `addToSystemPackages`, exports
              PROMETHEUS_HOME with environment.variables. That variable applies
              to the full system and replaces the PROMETHEUS_HOME of each other
              user. This module exports the variable for one user session
              only, which is the reason to use Home Manager.
            '';
          };

          gateway.enable = lib.mkEnableOption "the messaging gateway service (Telegram, Discord, Slack, ...)";
        };

      config = lib.mkIf cfg.enable (
        lib.mkMerge [

          # ── Merge MCP servers into settings ────────────────────────────
          (lib.mkIf (cfg.mcpServers != { }) {
            services.prometheus-agent.settings.mcp_servers = common.mcpServersToConfig cfg.mcpServers;
          })

          {
            assertions =
              common.pluginNameAssertions {
                inherit cfg;
                optionPath = "services.prometheus-agent";
              }
              ++ common.workspaceFilesAssertions {
                inherit cfg;
                opt = options.services.prometheus-agent.workingDirectory;
                optionPath = "services.prometheus-agent";
              };
          }

          # ── Packages and interactive-shell environment ─────────────────
          (lib.mkIf cfg.installPackage {
            home.packages = [ effectivePackage ] ++ cfg.extraPackages;
            home.sessionVariables.PROMETHEUS_HOME = cfg.prometheusHome;
          })

          # ── Activation: directories, config, secrets, documents ────────
          {
            # The activation runs after writeBoundary, when the home.file
            # symlinks are in place. It also runs after linkGeneration, when
            # Home Manager completes the switch. A secret that the activation
            # entry of sops-nix writes exists at that point.
            home.activation.prometheusAgentSetup =
              lib.hm.dag.entryAfter
                [
                  "writeBoundary"
                  "linkGeneration"
                ]
                (
                  common.mkStateScript {
                    inherit pkgs cfg;
                    inherit (cfg) prometheusHome workingDirectory;
                    run = "$DRY_RUN_CMD ";
                    stateDirs = common.stateSubdirs;
                    managedSystem = "home-manager";
                    # This state has one user. No group needs access to it.
                    modes = {
                      config = "0600";
                      env = "0600";
                      managed = "0600";
                      auth = "0600";
                      document = "0600";
                    };
                  }
                );
          }

          # ── Linux: systemd user services ───────────────────────────────
          (lib.mkIf (isLinux && cfg.gateway.enable) {
            systemd.user.services.prometheus-agent = mkUnit {
              description = "Prometheus Agent Gateway";
              argv = common.gatewayArgv cfg;
            };
          })

          (lib.mkIf (isLinux && cfg.backend.mode != "none") {
            systemd.user.services.prometheus-backend = mkUnit {
              description = common.backendDescription cfg;
              argv = common.backendArgv cfg;
            };
          })

          # ── Darwin: launchd agents ─────────────────────────────────────
          (lib.mkIf (isDarwin && cfg.gateway.enable) {
            launchd.agents.prometheus-agent = mkAgent {
              argv = common.gatewayArgv cfg;
              logName = "prometheus-agent";
            };
          })

          (lib.mkIf (isDarwin && cfg.backend.mode != "none") {
            launchd.agents.prometheus-backend = mkAgent {
              argv = common.backendArgv cfg;
              logName = "prometheus-backend";
            };
          })
        ]
      );
    };
}
