# 💬 Rede P2P

Este projeto é o Trabalho Final da disciplina de Sistemas Distribuídos (2025.2).
Trata-se de uma aplicação de chat P2P (peer-to-peer) em Python que utiliza um Coordenador para gerenciamento da rede. O sistema é robusto e tolerante a falhas, implementando a detecção de queda do Coordenador e a eleição de um novo líder através do **Algoritmo de Bully**.

## ✨ Funcionalidades Principais

* **Chat em Grupo:** Todos os nós conectados à rede podem enviar e receber mensagens em um chat comum.
* **Descoberta Dinâmica:** Um novo nó entra na rede enviando uma mensagem multicast (`JOIN_REQUEST`). O Coordenador responde via TCP com um UID (User ID) único, a lista de pares atual e o histórico de mensagens, persistindo essas informações ao decorrer do tempo.
* **Gerenciamento por Coordenador:** Um nó é designado como Coordenador, responsável por:
    * Atribuir UIDs a novos nós.
    * Manter a lista de pares (`peer_list`) sempre atualizada.
    * Enviar `HEARTBEATS` para que outros nós saibam que ele está ativo.
    * Verificar a saúde dos outros nós (`PING`).
* **Tolerância a Falhas (Coordenador):** Se o Coordenador falhar (parar de enviar `HEARTBEATS`), os outros nós detectam sua ausência após um `HEARTBEAT_TIMEOUT` e iniciam uma **Eleição de Coordenador** por meio do Algoritmo de Bully.
* **Tolerância a Falhas (Nós):** O Coordenador "pinga" (via TCP) periodicamente cada nó. Se um nó não responder depois de certo tempo, ele é removido da lista de pares e os demais são notificados.
* **Consistência de Histórico:** Ao entrar na rede, o novo nó recebe do Coordenador todo o histórico de mensagens, garantindo que ele tenha a mesma visão do chat que os pares mais antigos.
* **Saída Graciosa:** Um nó pode sair da rede digitando `exit`. Ele notifica o Coordenador (via TCP) antes de encerrar.

## 💻 Como Usar?

* Abra um terminal na sua máquina para cada nó que deseja adicionar a rede.
* Utilize o chat para interagir com os demais nós na rede.
* Caso queira desconectar um nó, digite 'exit' ou 'ctrl+c' para matar o terminal.
