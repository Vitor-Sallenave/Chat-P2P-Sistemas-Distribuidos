"""
        Trabalho Final

Autor: Vítor Sallenave Sales Milome
Disciplina: Sistemas Distribuídos 2025.2

"""

# Bibliotecas utilizadas
import socket, struct, json, threading
import time, sys, random

# Configurações de Rede:
MULTICAST_GROUP, MULTICAST_PORT = '224.1.1.1', 5007
TCP_PORT_BASE = 6000

# Configurações de Tolerância a Falhas:
# Obs.: os tempos foram escolhidos ponderando a rapidez de detectação de falhas e
# o controle do tráfego da rede, para que não houvesse um flood

# 1. Frequência de heartbeats enviados pelo Coordenador para cada nó da rede
# para avisar q está ativo
HEARTBEAT_INTERVAL = 5.0
# 2. Tempo que um nó (não coordenador) espera antes de declarar a
# falha/saída do Coordenador e iniciar uma nova eleição (Algoritmo de Bully)
HEARTBEAT_TIMEOUT = 15.0
# 3. Frequência de heartbeats enviados pelo Coordenador para cada nó para
# verificar o status desses e identificar falhas
PEER_HEALTH_CHECK_INTERVAL = 15.0

# Rede 2P2
class NoP2P:

    def __init__(self):
        # 1. Definindo a identificação do Nó
        self.my_uid = None
        self.is_coordinator = False
        self.coordinator_uid = None

        # 2. Definindo a lista de pares ativos e o histórico de mensagens
        # peer_list = {uid: (ip, tcp_port)}
        self.peer_list = {}
        self.message_history = []

        # 3. Flags de sincronização
        # Registra a última vez que o nó ouviu o Coordenador
        self.last_heartbeat_time = time.time()
        # Flag para evitar múltiplas eleições simultâneas
        self.election_in_progress = False
        # Flag para bloquear o envio de chat antes de ter um UID
        self.join_complete = False

        # 4. Definindo Sockets de envio e recebimento das mensagens multicast
        self.multicast_send_socket = self.setup_multicast_send_socket()
        self.multicast_listen_socket = self.setup_multicast_listen_socket()

        # 5. Encontra ip da máquina e uma porta para o nó
        self.my_ip = socket.gethostbyname(socket.gethostname())
        self.my_tcp_port = self.find_free_port()

        # 5. Define Socket para escutar conexões TCP da rede P2P
        # Usado para a resposta de Join, eleição e check dos status dos nós
        self.tcp_server_socket = self.setup_tcp_server_socket(self.my_ip,
                                                              self.my_tcp_port)

        # 6. Exibe iniciação do nó
        print(f"\n=== Nó iniciado ===\n")
        print(f"Ouvindo TCP em: {self.my_ip}:{self.my_tcp_port}")
        print(f"Grupo Multicast: {MULTICAST_GROUP}:{MULTICAST_PORT}\n")


    """ 1. Funções de configuração dos sockets do nó """

    # Configura o socket para enviar mensagens UDP multicast
    def setup_multicast_send_socket(self):
        # Pede ao Sistema Operacional um socket, define o protocolo como UDP
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM,
                             socket.IPPROTO_UDP)
        # Define opções do socket em nível do protocolo IP
        # Define o valor de TTL dos pacotes multicast, para alcancar
        # nós além da rede local
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

        return sock


    # Configura o socket para ouvir mensagens UDP multicast
    def setup_multicast_listen_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM,
                             socket.IPPROTO_UDP)
        # Permite que múltiplos processos escutem uma mesma porta
        # simultaneamente (Porta de multicast)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Escuta na porta 5007 em todas as interfaces de rede
        try:
            sock.bind(('', MULTICAST_PORT))
        except OSError as e:
            print(
                f"Erro ao bindar socket multicast: {e}. Verifique se outro processo está usando a porta {MULTICAST_PORT}")
            sys.exit(1)

        # Constrói o pacote de bytes multicast request
        mreq = struct.pack("4sl", socket.inet_aton(MULTICAST_GROUP),
                           socket.INADDR_ANY)
        # Adiciona o socket como um ouvinte do grupo
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        return sock


    # Encontra, aleatoriamente, uma porta livre na máquina
    def find_free_port(self):
        # Porta aleatória
        port = TCP_PORT_BASE + random.randint(0, 500)
        while True:
            try:
                # Tenta usar a porta
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.bind((self.my_ip, port))
                s.close()
                return port

            except OSError:
                # Se a porta estiver em uso, tenta a próxima
                port += 1
                if port > TCP_PORT_BASE + 1000:
                    raise IOError("Nenhuma porta livre encontrada! ")


    # Socket para ouvir conexões TCP (Nó atuando como sevidor na rede P2P)
    def setup_tcp_server_socket(self, ip, port):
        # Nesse caso, precisamos de uma mensagem de confirmação de que
        # o dado foi recebido, então é usado o TCP
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((ip, port))
        # Limite do backlog, suficiente para o contexto do trabalho
        sock.listen(5)

        return sock


    """ 2. Funções de chat """

    # Fecha todos os sockets do nó e encerra o programa
    def shutdown(self):
        print("\nEncerrando os sockets...")
        self.tcp_server_socket.close()
        self.multicast_listen_socket.close()
        self.multicast_send_socket.close()

        time.sleep(1)
        sys.exit(0)


    # Nó notifica o coordenador de sua saída da rede
    def leave_network(self):
        print("\n[Rede] Saindo da rede...")
        if (not self.is_coordinator) and (self.coordinator_uid in self.peer_list):
            try:
                coord_ip, coord_port = self.peer_list[self.coordinator_uid]
                print(f"[Rede] Notificando coordenador {self.coordinator_uid} da saída...")
                message = {
                    "type": "LEAVE_REQUEST",
                    "sender_uid": self.my_uid
                }
                self.send_tcp_message(coord_ip, coord_port, message)

            except Exception as e:
                print(f"[Erro] Não foi possível notificar o coordenador da saída: {e}")

        # Fecha conexões
        self.shutdown()


    # Loop principal (bloqueante) para o usuário enviar mensagens
    def start_chat_loop(self):
        while not self.join_complete:
            # Espera até que o nó tenha um UID
            time.sleep(0.5)

        print("\n=== Chat Iniciado ===\n")
        print("Digite sua mensagem ou digite 'exit' para sair: ")
        while True:
            try:
                # Entrada do usuário
                message_content = input("M: ")

                if message_content.lower() == 'exit':
                    # Nó sai da rede
                    self.leave_network()
                    break

                if message_content:
                    message = {
                        "type": "CHAT_MESSAGE",
                        "sender_uid": self.my_uid,
                        "content": message_content
                    }
                    self.send_multicast(message)
            except KeyboardInterrupt:
                break

        # Encerra o programa
        print("Encerrando os sockets...")
        self.tcp_server_socket.close()
        self.multicast_listen_socket.close()
        self.multicast_send_socket.close()
        sys.exit(0)


    # Verifica se o coordenador ainda está ativo
    def check_coordinator_heartbeat(self):
        while True:
            # Verifica a cada segundo se o timeout foi execedido
            time.sleep(1.0)

            if self.join_complete and not self.is_coordinator and not self.election_in_progress:
                time_since_heartbeat = time.time() - self.last_heartbeat_time

                if time_since_heartbeat > HEARTBEAT_TIMEOUT:
                    print(f"[FALHA] Coordenador (UID: {self.coordinator_uid}) caiu. Timeout!")
                    self.start_election()
                    # Resetamos o timer para não iniciar eleições múltiplas
                    self.last_heartbeat_time = time.time()


    # Se autodeclara o primeiro coordenador
    def become_first_coordinator(self):
        # Atualiza propriedades
        self.my_uid = 1
        self.is_coordinator = True
        self.coordinator_uid = 1
        self.peer_list[self.my_uid] = (self.my_ip, self.my_tcp_port)
        self.join_complete = True

        # Inicia tarefas de coordenador
        threading.Thread(target=self.send_heartbeat, daemon=True).start()
        threading.Thread(target=self.check_peer_health, daemon=True).start()


    # Um nó tenta entrar na rede por uma mensagem multicast
    def join_network(self):
        print("[Rede] Tentando entrar na rede...")
        message = {
            "type": "JOIN_REQUEST",
            "port": self.my_tcp_port
        }
        self.send_multicast(message)

        # Espera 5 segundos por uma resposta (JOIN_RESPONSE)
        time.sleep(5)

        # Ninguém respondeu. Logo, o nó atual é o primeiro a entrar
        if not self.join_complete:
            print("[Rede] Ninguém me respondeu. Sou o primeiro nó e Coordenador.")
            self.become_first_coordinator()


    # Coordenador processa a entrada um novo nó e avisa os demais da rede
    def handle_join_request(self, new_node_ip, new_node_port):
        # Encontra o maior UID atual e soma 1
        new_uid = max(self.peer_list.keys()) + 1 if self.peer_list else 1
        # Adiciona o novo nó à lista de pares
        self.peer_list[new_uid] = (new_node_ip, new_node_port)
        print(f"[Rede] Atribuindo UID {new_uid} para {new_node_ip}:{new_node_port}")
        # Envia a resposta tcp para o novo nó com as informações de sua configuração
        response_message = {
            "type": "JOIN_RESPONSE",
            "your_uid": new_uid,
            "coordinator_uid": self.my_uid,
            "peer_list": self.peer_list,
            "history": self.message_history
        }
        self.send_tcp_message(new_node_ip, new_node_port, response_message)

        # Informa os outros nós sobre o novo nó na rede
        update_message = {
            "type": "PEER_LIST_UPDATE",
            "peer_list": self.peer_list,
            "removed_uid": None
        }
        self.send_multicast(update_message)


    # Roteador para mensagens Multicast
    def handle_message(self, message, addr):
        msg_type = message.get("type")

        # 1. Entrada na Rede (Resposta do Coordenador)
        if msg_type == "JOIN_REQUEST":
            if self.is_coordinator:
                print(f"\n[Rede] Novo nó querendo entrar na rede ({addr[0]}:{message.get('port')})")
                self.handle_join_request(addr[0], message.get('port'))

        # 2. Heartbeat
        elif msg_type == "HEARTBEAT":
            if message.get("coordinator_uid") == self.coordinator_uid:
                # Registra a última vez que o coordenador visto
                self.last_heartbeat_time = time.time()

        # 3. Histórico Consistente (Chat)
        elif msg_type == "CHAT_MESSAGE":
            # Adiciona mensagem ao histórico e a exibe
            sender_uid = message.get("sender_uid")
            content = message.get("content")
            if sender_uid != self.my_uid:
                print(f"\n[{sender_uid}]: {content}")
            self.message_history.append(message)

        # 4. Atualização da lista de pares
        elif msg_type == "PEER_LIST_UPDATE":
            # O coordenador informando a rede de um novo nó
            new_peer_list = message.get("peer_list")
            self.peer_list = {int(k): v for k, v in new_peer_list.items()}

            # Verifica se um nó foi removido
            removed_uid = message.get("removed_uid")
            if removed_uid:
                print(f"[Rede] O Nó {removed_uid} saiu. Lista de pares atualizada: {list(self.peer_list.keys())}")
            else:
                # Na verdade, um nó está entrando
                if self.join_complete:
                    print(f"\b[Rede] Nó entrou. Lista de pares atualizada: {list(self.peer_list.keys())}")


    # Se mantém a espera de uma mensagem multicast no grupo
    def listen_multicast(self):
        while True:
            try:
                data, addr = self.multicast_listen_socket.recvfrom(1024)
                message_data = json.loads(data.decode('utf-8'))
                # Chama função para tratar mensagem
                self.handle_message(message_data, addr)
            except Exception as e:
                print(f"[Erro Multicast Listen]: {e}")


    # Coordenador remove nó da lista de nós ativos
    def remove_node(self, uid_to_remove):
        if not self.is_coordinator:
            return

        if uid_to_remove in self.peer_list:
            removed_node_info = self.peer_list.pop(uid_to_remove, None)
            if removed_node_info:
                print(f"[Rede] Nó {uid_to_remove} removido da lista de pares.")
                update_message = {
                    "type": "PEER_LIST_UPDATE",
                    "peer_list": self.peer_list,
                    "removed_uid": uid_to_remove
                }
                # Considerando a criticidade e frequência da operação na rede,
                # decidi aproveitar a rapidez do UPD nesse caso
                self.send_multicast(update_message)
        else:
            # Pode acontecer se as funções de health check e de saída do nó
            # tentarem remover o mesmo nó ao mesmo tempo
            print(f"[Rede] Tentativa de remover nó {uid_to_remove} que não está na lista.")
            pass


    # Coordenador checa se os outros nós estão ativos (ping)
    def check_peer_health(self):
        while self.is_coordinator:
            time.sleep(PEER_HEALTH_CHECK_INTERVAL)
            if not self.is_coordinator:
                break

            nodes_to_remove = []
            for uid, (ip, port) in list(self.peer_list.items()):
                # Não checa a si mesmo
                if uid == self.my_uid:
                    continue

                # Tenta enviar um ping
                ping = self.send_tcp_message(ip, port, {"type": "PING"})
                if not ping:
                    print(f"\n[Health Check] Nó {uid} ({ip}:{port}) não respondeu ao PING e deve estar inativo.")
                    nodes_to_remove.append(uid)

            # Remove os nós inativos
            if nodes_to_remove:
                print(f"[Health Check] Removendo nós: {nodes_to_remove}")
                for uid in nodes_to_remove:
                    self.remove_node(uid)


    # Serializa e envia dados para o grupo multicast
    def send_multicast(self, message_data):
        try:
            message_json = json.dumps(message_data)
            # Envia os bytes para o grupo
            self.multicast_send_socket.sendto(message_json.encode('utf-8'),
                                              (MULTICAST_GROUP, MULTICAST_PORT))
        except Exception as e:
            print(f"[Erro MCAST Send]: {e}")


    # Coordenador envia heartbeat para demais nós para indicar q está ativo
    def send_heartbeat(self):
        while self.is_coordinator:
            message = {
                "type": "HEARTBEAT",
                "coordinator_uid": self.my_uid
            }
            self.send_multicast(message)
            time.sleep(HEARTBEAT_INTERVAL)


    # Atualiza propriedades do nó que ganhou a eleição e se tornará o novo coordenador
    def win_election(self):
        print(f"[Eleição] O novo coordenador é UID: {self.my_uid}!")
        self.is_coordinator = True
        self.coordinator_uid = self.my_uid
        self.election_in_progress = False

        # Começa a enviar heartbeats
        threading.Thread(target=self.send_heartbeat, daemon=True).start()
        threading.Thread(target=self.check_peer_health, daemon=True).start()

        # 2. Anuncia o novo status de coordenador para todos os demais nós da rede
        # usando o tcp para garantir a confiabilidade da entrega
        victory_message = {
            "type": "COORDINATOR",
            "new_coordinator_uid": self.my_uid
        }

        for uid, (ip, port) in self.peer_list.items():
            if uid != self.my_uid:
                self.send_tcp_message(ip, port, victory_message)


    # Envia uma mensagem TCP para um nó específico
    def send_tcp_message(self, target_ip, target_port, message_data):
        try:
            # Cria um socket de curta duração para enviar a mensagem
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                # Define um tempo para as operações bloqueantes do socket
                sock.settimeout(3.0)
                sock.connect((target_ip, target_port))
                # Converte o dicionário em uma string JSON
                message_json = json.dumps(message_data)
                # Converte a string json em bytes para se comunicar com a rede e
                # garante que toda a mensagem seja enviada
                sock.sendall(message_json.encode('utf-8'))
                return True
        except (socket.timeout, socket.error) as e:
            print(f"\nFalha ao conectar com {target_ip}:{target_port}.")
            return False


    # Algoritmo do Bully
    def start_election(self):
        if self.election_in_progress:
            return

        print(f"[Eleição] Iniciando uma eleição para novo coordenador (UID: {self.my_uid})")
        self.election_in_progress = True

        # Encontra todos os pares com UID MAIOR
        higher_peers = []
        for uid, (ip, port) in self.peer_list.items():
            if uid > self.my_uid:
                higher_peers.append((uid, ip, port))

        if not higher_peers:
            # Não há ninguém com UID maior, então o nó atual é eleito
            self.win_election()
            return

        # Envia mensagem "ELECTION" para todos os UID maiores
        sent_to_anyone = False
        for uid, ip, port in higher_peers:
            print(f"[Eleição] Enviando ELECTION para UID {uid} em {ip}:{port}")
            if self.send_tcp_message(ip, port, {"type": "ELECTION",
                                                "sender_uid": self.my_uid}):
                sent_to_anyone = True

        if not sent_to_anyone:
            # Não conseguiu contatar nenhum nó maior
            print("[Eleição] Não consegui contatar nenhum nó maior.")
            self.win_election()
        else:
            print("[Eleição] Aguardando resposta de nós maiores...")


    # Roteador para mensagens TCP (P2P)
    def handle_tcp_client(self, conn, addr):
        try:
            with conn:
                # Recebe dados da conexão ao servidor tcp (chamada bloqueante)
                # Define tamanho do buffer
                data = conn.recv(4096)
                if not data:
                    return
                # Decodifica os bytes da mensagem e armazena em um dict
                message = json.loads(data.decode('utf-8'))

                # Pega o tipo de mensagem em questão
                msg_type = message.get("type")

                # 1. Entrada na Rede
                if msg_type == "JOIN_RESPONSE":
                    # Já estamos na rede
                    if self.join_complete: return

                    # Atualiza propriedades do novo nó com informações
                    # vindas do Coordenador
                    self.my_uid = message.get("your_uid")
                    self.coordinator_uid = message.get("coordinator_uid")
                    self.peer_list = {int(k): v for k, v in message.get("peer_list").items()}
                    self.message_history = message.get("history", [])
                    # A partir daqui, o usuário já pode participar do chat
                    self.join_complete = True

                    print(f"[Rede] Conectado com sucesso! UID: {self.my_uid}")
                    print(f"[Rede] Coordenador atual: {self.coordinator_uid}")
                    print(f"[Rede] Pares na rede: {list(self.peer_list.keys())}")
                    print("\n=== Histórico de Mensagens ===\n")
                    for msg in self.message_history:
                        print(f"  [{msg.get('sender_uid')}]: {msg.get('content')}")
                    print("--------------------------------")

                # 2. Eleição
                elif msg_type == "ELECTION":
                    # 2.1 Alguém com UID menor iniciou/deu continuidade a eleição
                    sender_uid = message.get("sender_uid")
                    print(f"[Eleição] Recebi ELECTION de UID: {sender_uid}")
                    response = {"type": "OK"}
                    # Encontra a porta de escuta correta do remetente
                    sender_info = self.peer_list.get(sender_uid)
                    if sender_info:
                        self.send_tcp_message(sender_info[0], sender_info[1], response)

                    # 2.2 O nó inicia a eleição
                    if not self.election_in_progress and not self.is_coordinator:
                        self.start_election()

                elif msg_type == "OK":
                    # Alguém com UID maior respondeu a eleição
                    print(f"[Eleição] Recebi OK. Desistindo da eleição.")
                    self.election_in_progress = False

                elif msg_type == "COORDINATOR":
                    # A eleição foi vencida
                    new_coordinator_uid = message.get("new_coordinator_uid")
                    print(f"[Eleição] FIM. O novo coordenador é UID: {new_coordinator_uid}")
                    self.coordinator_uid = new_coordinator_uid
                    self.is_coordinator = (self.my_uid == new_coordinator_uid)

                    # Se o nó atual ganhou, começa a enviar heartbeats
                    if self.is_coordinator:
                        threading.Thread(target=self.send_heartbeat,
                                         daemon=True).start()

                    self.election_in_progress = False
                    self.last_heartbeat_time = time.time()
        except Exception as e:
            print(f"[Erro TCP Handle]: {e}")


    # O socket de escuta tcp entre em espera de uma conexão
    def listen_tcp(self):
        while True:
            try:
                # Chamada bloqueante
                conn, addr = self.tcp_server_socket.accept()
                # A função de handle cuida da chamada a partir das informações
                # obtidas anteriormente. Caso o programa seja encerrado, o thread
                # também é (daemeon = true).
                threading.Thread(target=self.handle_tcp_client,
                                 args=(conn, addr), daemon=True).start()
            except Exception as e:
                break


    # Inicia os threads
    def start(self):
        # Threads para ouvir conexões TCP e ouvir mensagens Multicast
        threading.Thread(target=self.listen_tcp, daemon=True).start()
        threading.Thread(target=self.listen_multicast, daemon=True).start()

        # Tenta entrar na rede
        self.join_network()

        # Thread para verificar a vida do coordenador
        threading.Thread(target=self.check_coordinator_heartbeat,
                         daemon=True).start()

        # Loop principal para entrada de chat do usuário
        self.start_chat_loop()


if __name__ == "__main__":
    node = NoP2P()
    node.start()