-- Execute conectado ao banco administrativo `postgres`, com uma role admin.
-- Crie a role e o banco uma única vez. Não use `triton` nem a role da aplicação.
--
-- 1) Execute somente esta instrução para criar a role exclusiva de teste:
CREATE ROLE triton_integration_test LOGIN;

-- 2) Defina uma senha local sem gravá-la neste arquivo:
--    psql:   \password triton_integration_test
--    pgAdmin: configure a senha nas propriedades da role.
--
-- 3) Em uma execução separada (CREATE DATABASE não pode estar numa transação),
--    conectado ao banco `postgres`, crie o banco isolado:
CREATE DATABASE triton_integration_test OWNER triton_integration_test;

-- A role proprietária do banco pode criar o schema público e os objetos Alembic.
-- Não remova/recrie o banco se ele já existir; confira seu uso e a revisão primeiro.
