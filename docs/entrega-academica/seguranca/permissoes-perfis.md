# Perfis e permissões — demonstração

Executado em 2026-11-16T14:43:55+00:00 num banco temporário (`demonstrar_perfis.py`).
✓ = permitido; ✗ = recusado (403 = perfil sem permissão; 401 = sem chave). 400/404/409 contam como permitido: a API aceitou o perfil e recusou só os dados de teste.

| Perfil | Ver locais | Ver caixa de notas recebidas | Criar local | Lançar nota | Decidir no SIG | Usar ordens de serviço | Fazer backup do banco | Administrar usuários |
|---|---|---|---|---|---|---|---|---|
| Administrador | ✓ 200 | ✓ 200 | ✓ 201 | ✓ 400 | ✓ 400 | ✓ 200 | ✓ 200 | ✓ 200 |
| Gerente (Maciel) | ✓ 200 | ✓ 200 | ✓ 201 | ✓ 400 | ✓ 400 | ✓ 200 | ✓ 200 | ✗ 403 |
| Operador (Jonata) | ✓ 200 | ✓ 200 | ✓ 201 | ✓ 400 | ✗ 403 | ✓ 200 | ✗ 403 | ✗ 403 |
| Leitura (auditoria) | ✓ 200 | ✓ 200 | ✗ 403 | ✗ 403 | ✗ 403 | ✗ 403 | ✗ 403 | ✗ 403 |
| Leitura + ordens de serviço (ajuste individual) | ✓ 200 | ✓ 200 | ✗ 403 | ✗ 403 | ✗ 403 | ✓ 200 | ✗ 403 | ✗ 403 |
| Sem chave | ✓ 200 | ✓ 200 | ✗ 401 | ✗ 401 | ✗ 401 | ✗ 401 | ✗ 401 | ✗ 401 |

Auditoria: 33 registros, 15 recusas (quem, ação, funcionalidade, resultado). Ver `evidence/permissoes-perfis.json`.
