FROM node:20

ARG TZ
ENV TZ="$TZ"

ARG CLAUDE_CODE_VERSION=latest

# Install basic development tools and iptables/ipset
RUN apt-get update && apt-get install -y --no-install-recommends \
  less \
  git \
  procps \
  sudo \
  fzf \
  man-db \
  unzip \
  gnupg2 \
  gh \
  iptables \
  ipset \
  iproute2 \
  dnsutils \
  aggregate \
  jq \
  curl \
  nano \
  vim \
  python3 \
  python3-pip \
  python3-venv \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

# Ensure default node user has access to /usr/local/share
RUN mkdir -p /usr/local/share/npm-global && \
  chown -R node:node /usr/local/share

ARG USERNAME=node

# Persist bash history.
RUN SNIPPET="export PROMPT_COMMAND='history -a' && export HISTFILE=/commandhistory/.bash_history" \
  && mkdir /commandhistory \
  && touch /commandhistory/.bash_history \
  && chown -R $USERNAME /commandhistory

# Set `DEVCONTAINER` environment variable to help with orientation
ENV DEVCONTAINER=true

# Create workspace and config directories and set permissions
RUN mkdir -p /workspace /home/node/.claude && \
  chown -R node:node /workspace /home/node/.claude

WORKDIR /workspace

ARG GIT_DELTA_VERSION=0.18.2
RUN ARCH=$(dpkg --print-architecture) && \
  wget "https://github.com/dandavison/delta/releases/download/${GIT_DELTA_VERSION}/git-delta_${GIT_DELTA_VERSION}_${ARCH}.deb" && \
  sudo dpkg -i "git-delta_${GIT_DELTA_VERSION}_${ARCH}.deb" && \
  rm "git-delta_${GIT_DELTA_VERSION}_${ARCH}.deb"

# Install Starship prompt
ARG STARSHIP_VERSION=1.21.1
RUN curl -fsSL https://starship.rs/install.sh | sh -s -- -y -v v${STARSHIP_VERSION}

# Set up non-root user
USER node

# Add /home/node/.local to PATH
ENV PATH=$PATH:/home/node/.local/bin

# Install pipx and pre-commit
RUN pip install --user --break-system-packages pipx && \
  pipx install pre-commit

# Install global packages
ENV NPM_CONFIG_PREFIX=/usr/local/share/npm-global
ENV PATH=$PATH:/usr/local/share/npm-global/bin

# Set the default shell to bash rather than sh
ENV SHELL=/bin/bash

# Set the default editor and visual
ENV EDITOR=nano
ENV VISUAL=nano

# Copy Starship config
RUN mkdir -p /home/node/.config
COPY --chown=node:node dotfiles/starship.toml /home/node/.config/starship.toml

# Configure bash with fzf and Starship prompt
RUN echo '\n\
# fzf integration\n\
[ -f /usr/share/doc/fzf/examples/key-bindings.bash ] && source /usr/share/doc/fzf/examples/key-bindings.bash\n\
[ -f /usr/share/bash-completion/completions/fzf ] && source /usr/share/bash-completion/completions/fzf\n\
\n\
# Starship prompt\n\
eval "$(starship init bash)"\n\
\n\
# History persistence\n\
export PROMPT_COMMAND="${PROMPT_COMMAND:+$PROMPT_COMMAND;}history -a"\n\
export HISTFILE=/commandhistory/.bash_history\n\
' >> ~/.bashrc

# Add bashrc.d directory to .bashrc
RUN echo '\n\
# >>> bashrc.d integration >>>\n\
if [ -d "$HOME/.bashrc.d" ]; then\n\
  for file in "$HOME/.bashrc.d/"*; do\n\
    [ -r "$file" ] && [ -f "$file" ] && source "$file"\n\
  done\n\
  unset file\n\
fi\n\
# <<< bashrc.d integration <<<\n\
' >> ~/.bashrc

# Create bashrc.d directory and set permissions
RUN mkdir -p /home/node/.bashrc.d && \
  chown -R node:node /home/node/.bashrc.d && \
  chmod 0755 /home/node/.bashrc.d

# Copy bashrc.d files
COPY --chown=node:node .bashrc.d/ /home/node/.bashrc.d/

# Install uv as node user
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
  chown -R node:node /home/node/.local && \
  chmod 0755 /home/node/.local


# Install Claude
#### OLD INSTALL METHOD ####
# RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}
#### NEW INSTALL METHOD ####
RUN curl -fsSL https://claude.ai/install.sh | bash

# Install Plannotator CLI
RUN curl -fsSL https://plannotator.ai/install.sh | bash

# Install OpenSpec
RUN npm install -g @fission-ai/openspec@latest

# Install OpenCode
RUN npm install -g opencode-ai@latest

# Install Spec-Kit
RUN uv tool install specify-cli --from git+https://github.com/github/spec-kit.git

# Install kubectl
RUN curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" && \
  chmod +x kubectl && \
  mv kubectl /home/node/.local/bin/kubectl

# Install Helm
RUN curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-4 && \
  chmod +x get_helm.sh && \
  HELM_INSTALL_DIR=/home/node/.local/bin USE_SUDO=false ./get_helm.sh && \
  rm get_helm.sh

# Install oc (https://mirror.openshift.com/pub/openshift-v4/x86_64/clients/ocp/stable/openshift-client-linux.tar.gz)
RUN curl -LO "https://mirror.openshift.com/pub/openshift-v4/x86_64/clients/ocp/stable/openshift-client-linux.tar.gz" && \
  tar -xzf openshift-client-linux.tar.gz && \
  mv oc /home/node/.local/bin/oc && \
  rm openshift-client-linux.tar.gz

# Install direnv (script installs directly to first writable PATH directory)
RUN bin_path=/home/node/.local/bin curl -sfL https://direnv.net/install.sh | bash

# Configure direnv
# RUN direnv allow /workspace
  
# Copy and set up firewall script
# COPY scripts/init-firewall.sh /usr/local/bin/
# USER root
# RUN chmod +x /usr/local/bin/init-firewall.sh && \
#   echo "node ALL=(root) NOPASSWD: /usr/local/bin/init-firewall.sh" > /etc/sudoers.d/node-firewall && \
#   chmod 0440 /etc/sudoers.d/node-firewall

USER node