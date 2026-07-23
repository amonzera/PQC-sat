# Dependência local wolfSSL

O experimento `KEX_FAIR_V1` exige wolfSSL 5.9.2, commit upstream
`ac01707f552c611fbd135cc723b2682b3e7f80f2`, preparado no formato de
biblioteca Arduino. A árvore usada no build atual veio do repositório oficial
sob GPLv3; uma distribuição comercial equivalente também pode ser usada se a
organização possuir essa licença.

O código da dependência não faz parte do Git deste projeto. Copie o diretório
`IDE/ARDUINO/wolfssl/` da revisão indicada para:

```text
firmware/lib/wolfssl/
├── library.properties
└── src/
    ├── wolfssl/
    └── wolfcrypt/
```

O pacote não deve fornecer outro `src/user_settings.h`; a configuração única é
a rastreada em `firmware/esp32_serial_spike/user_settings.h`. A compilação
limpa deve usar:

```bash
python3 -m platformio run -e robocore_wisdom_esp32_fair -t clean
python3 -m platformio run -e robocore_wisdom_esp32_fair
```

Esse ambiente falha de propósito quando a dependência não está presente. O
ambiente `robocore_wisdom_esp32` preserva apenas o firmware legado e não
anuncia `kex=FAIR_V1`.

O manifesto de deploy registra a versão, o commit esperado e o SHA-256
determinístico da árvore local. Para a árvore atual, são 327 arquivos e
`tree_sha256=6e7bc3f25de37caf014b5620b1d5804609ccd6bef70a07b004aba3eb130e8a6a`.

Antes de distribuir código-fonte ou binário, cumpra a GPLv3 da árvore atual ou
os termos da licença comercial efetivamente contratada. O build reproduzível
não altera nem substitui essas obrigações.
