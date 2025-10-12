# Discord Self-Bot Monitor - Setup Completo

⚠️ **AVISO IMPORTANTE**: Este projeto é apenas para fins acadêmicos e educacionais. Self-bots violam os Termos de Serviço do Discord e podem resultar no banimento da sua conta.

## 🎯 O que este projeto faz

Este sistema monitora mensagens em canais do Discord em tempo real e transmite os dados para um servidor HTTP local, onde você pode visualizar através de uma interface web moderna.

**Funcionalidades:**
- ✅ Monitora mensagens em tempo real
- ✅ Captura edições e deleções de mensagens
- ✅ Interface web com dashboard ao vivo
- ✅ Filtros por canais específicos
- ✅ Logging detalhado
- ✅ Histórico de mensagens
- ✅ WebSocket para atualizações em tempo real

## 📋 Pré-requisitos

- Python 3.8 ou superior
- Uma conta Discord (⚠️ use uma conta secundária/teste)
- Conhecimentos básicos de Python

## 🚀 Instalação

### 1. Clone e configure o ambiente

```bash
# Navegue até o diretório do discord.py-self
cd /home/baia/git/discord.py-self

# Crie um ambiente virtual (recomendado)
python3 -m venv venv
source venv/bin/activate

# Instale as dependências do discord.py-self
python3 -m pip install -e .

# Instale dependências adicionais para o monitor
pip install aiohttp flask flask-socketio
```

### 2. Como obter seu Token de Usuário Discord

⚠️ **CUIDADO**: Nunca compartilhe seu token com ninguém!

**Método 1 - Via DevTools do Navegador:**

1. Abra o Discord no navegador (discord.com)
2. Faça login na sua conta
3. Pressione `F12` para abrir DevTools
4. Vá para a aba `Network`
5. Pressione `Ctrl+R` para recarregar a página
6. Procure por requisições para `discord.com/api`
7. Clique em uma requisição e vá para `Headers`
8. Procure por `Authorization: TOKEN_AQUI`
9. Copie o token (sem a palavra "Authorization:")

**Método 2 - Via Console JavaScript:**

1. Abra o Discord no navegador
2. Pressione `F12` → Console
3. Cole este código:
```javascript
window.webpackChunkdiscord_app.push([
  [Math.random()], 
  {}, 
  req => {
    for (let m of Object.keys(req.c).map(x => req.c[x].exports).filter(x => x)) {
      if (m.default && m.default.getToken !== undefined) {
        return copy(m.default.getToken());
      }
      if (m.getToken !== undefined) {
        return copy(m.getToken());
      }
    }
  }
]);
console.log("Token copiado para clipboard!");
```

### 3. Como obter IDs dos Canais

1. No Discord, vá em `Configurações → Avançado`
2. Ative `Modo Desenvolvedor`
3. Clique com botão direito no canal desejado
4. Selecione `Copiar ID`

## ⚙️ Configuração

### 1. Configure o Self-Bot

Edite o arquivo `selfbot_monitor.py`:

```python
# Linha ~185 - Adicione seu token
TOKEN = "SEU_TOKEN_AQUI"  # ⚠️ Cole seu token aqui

# Linha ~188 - Configure canais (opcional)
TARGET_CHANNELS = [
    1234567890123456789,  # ID do canal 1
    9876543210987654321,  # ID do canal 2
    # Deixe vazio [] para monitorar TODOS os canais
]
```

### 2. Configure o servidor local (opcional)

O servidor local roda na porta 3000 por padrão. Se quiser alterar, edite `local_server.py`:

```python
# Linha final do arquivo
socketio.run(app, host='0.0.0.0', port=3000)  # Altere a porta aqui
```

## 🎮 Como usar

### 1. Inicie o servidor local

```bash
# Terminal 1
python3 local_server.py
```

Você verá:
```
🚀 Iniciando servidor HTTP local...
📱 Dashboard disponível em: http://localhost:3000
🔌 Endpoint para self-bot: http://localhost:3000/discord-message
```

### 2. Abra o dashboard no navegador

Acesse: http://localhost:3000

### 3. Inicie o self-bot

```bash
# Terminal 2 (novo terminal)
python3 selfbot_monitor.py
```

Você verá:
```
🟢 Self-bot conectado como: SeuNome (ID: 123456789)
📡 Monitorando canais: [123456789012345678]
🌐 Enviando dados para: http://localhost:3000
```

### 4. Monitore as mensagens

- Abra o Discord e envie mensagens nos canais configurados
- Veja as mensagens aparecerem em tempo real no dashboard
- Teste edições e deleções de mensagens

## 📊 Interface Web

O dashboard mostra:

- **Status de conexão** - Se o self-bot está ativo
- **Mensagens em tempo real** - Com autor, canal, servidor
- **Edições de mensagens** - Antes e depois
- **Deleções de mensagens** - Conteúdo deletado
- **Controles** - Limpar histórico, auto-scroll
- **Informações contextuais** - Servidor, canal, timestamps

## 🛠️ Estrutura dos arquivos

```
discord.py-self/
├── selfbot_monitor.py      # Self-bot que monitora Discord
├── local_server.py         # Servidor HTTP com dashboard
├── requirements.txt        # Dependências do discord.py-self
└── README_SELFBOT.md      # Este arquivo
```

## 🔧 Parâmetros Configuráveis

### Self-Bot (`selfbot_monitor.py`)

```python
TOKEN = "..."                    # Seu token Discord
LOCALHOST_URL = "http://..."     # URL do servidor local
TARGET_CHANNELS = [...]          # IDs dos canais (vazio = todos)
```

### Servidor Local (`local_server.py`)

```python
MAX_HISTORY = 1000              # Máx. mensagens em memória
port=3000                       # Porta do servidor
```

## 📝 Logs

Os logs são salvos em:
- `selfbot.log` - Logs do self-bot
- Console do servidor - Logs do servidor HTTP

## ⚠️ Limitações e Avisos

### Limitações Técnicas
- Não consegue ver mensagens em canais sem permissão
- Rate limits do Discord podem causar delays
- WebSocket pode desconectar em redes instáveis

### Avisos Legais
- **Self-bots violam os ToS do Discord**
- **Risco de banimento da conta**
- **Use apenas para fins educacionais**
- **Não monitore conversas sem consentimento**
- **Respeite a privacidade dos usuários**

## 🐛 Troubleshooting

### Self-bot não conecta
```bash
# Verifique se o token está correto
# Verifique se não há 2FA ativo
# Verifique se a conta não está limitada
```

### Servidor local não inicia
```bash
# Verifique se a porta 3000 está livre
sudo netstat -tlnp | grep :3000

# Use outra porta se necessário
python3 local_server.py  # Edite o código para mudar porta
```

### Mensagens não aparecem
```bash
# Verifique se os IDs dos canais estão corretos
# Verifique se o self-bot tem acesso aos canais
# Verifique os logs: tail -f selfbot.log
```

### Dashboard não carrega
```bash
# Limpe cache do navegador
# Tente outro navegador
# Verifique console do navegador (F12)
```

## 🔒 Segurança

- **Nunca compartilhe seu token**
- **Use apenas em redes confiáveis**
- **Não deixe o sistema rodando 24/7**
- **Use uma conta secundária**
- **Mantenha logs seguros**

## 📚 Recursos Adicionais

- [Documentação Discord.py-self](https://discordpy-self.readthedocs.io/)
- [API Discord](https://discord.com/developers/docs)
- [Flask Documentation](https://flask.palletsprojects.com/)

## 🤝 Contribuição

Este é um projeto educacional. Se encontrar bugs ou melhorias:

1. Teste em ambiente isolado
2. Documente o problema/solução
3. Mantenha o foco educacional

---

**Lembre-se**: Use com responsabilidade e apenas para aprendizado! 🎓