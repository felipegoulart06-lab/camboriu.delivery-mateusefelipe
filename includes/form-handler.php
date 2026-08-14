<?php
declare(strict_types=1);

function handle_contact_form(): array
{
    $result = [
        'success' => false,
        'message' => '',
        'old' => [
            'name' => '',
            'company' => '',
            'email' => '',
            'phone' => '',
            'segment' => '',
            'message' => '',
        ],
    ];

    if ($_SERVER['REQUEST_METHOD'] !== 'POST' || !isset($_POST['contact_submit'])) {
        return $result;
    }

    $name = trim((string) ($_POST['name'] ?? ''));
    $company = trim((string) ($_POST['company'] ?? ''));
    $email = trim((string) ($_POST['email'] ?? ''));
    $phone = trim((string) ($_POST['phone'] ?? ''));
    $segment = trim((string) ($_POST['segment'] ?? ''));
    $message = trim((string) ($_POST['message'] ?? ''));

    $result['old'] = compact('name', 'company', 'email', 'phone', 'segment', 'message');

    if ($name === '' || $company === '' || $email === '' || $phone === '') {
        $result['message'] = 'Preencha os campos obrigatórios para continuar.';
        return $result;
    }

    if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        $result['message'] = 'Informe um e-mail corporativo válido.';
        return $result;
    }

    $allowedSegments = [
        'clinica',
        'laboratorio',
        'farmacia',
        'juridico',
        'financeiro',
        'varejo',
        'outro',
    ];

    if ($segment !== '' && !in_array($segment, $allowedSegments, true)) {
        $result['message'] = 'Selecione um segmento válido.';
        return $result;
    }

    $storageDir = dirname(__DIR__) . '/storage';
    if (!is_dir($storageDir)) {
        mkdir($storageDir, 0755, true);
    }

    $entry = [
        'created_at' => date('c'),
        'name' => $name,
        'company' => $company,
        'email' => $email,
        'phone' => $phone,
        'segment' => $segment,
        'message' => $message,
        'ip' => $_SERVER['REMOTE_ADDR'] ?? 'unknown',
    ];

    $line = json_encode($entry, JSON_UNESCAPED_UNICODE) . PHP_EOL;
    $saved = file_put_contents($storageDir . '/leads.jsonl', $line, FILE_APPEND | LOCK_EX);

    if ($saved === false) {
        $result['message'] = 'Não foi possível registrar sua solicitação. Tente novamente.';
        return $result;
    }

    $result['success'] = true;
    $result['message'] = 'Solicitação recebida. Nossa equipe comercial retorna em até 1 dia útil.';
    $result['old'] = [
        'name' => '',
        'company' => '',
        'email' => '',
        'phone' => '',
        'segment' => '',
        'message' => '',
    ];

    return $result;
}
