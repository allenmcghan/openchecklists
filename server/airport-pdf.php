<?php
// Deployed at: api.openchecklists.net/airport-pdf.php  (kw3, cPanel user openchkl,
//   docroot /home/openchkl/public_html). NOT auto-deployed — copy this file up by
//   hand when it changes.
//
// Emails a client-generated airport PDF as an attachment. Called SERVER-TO-SERVER
// by the ocl-api Worker only (POST /api/airport/email-pdf), because the browser
// can't call here directly: the server injects a second wildcard CORS header, so
// browser CORS fails. The Worker holds the shared secret.
//
// The real secret lives in the Worker secret OCL_PDF_SECRET and in the deployed
// copy of this file; it is REDACTED here. Set the deployed copy's value to match
// the Worker secret.
header('Content-Type: application/json');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(204); exit; }
if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); echo '{"error":"method"}'; exit; }
if (($_SERVER['HTTP_X_OCL_SECRET'] ?? '') !== 'REDACTED-SET-TO-OCL_PDF_SECRET') {
    http_response_code(403); echo '{"error":"forbidden"}'; exit;
}

$raw = file_get_contents('php://input');
$d = json_decode($raw, true);
if (!$d) { http_response_code(400); echo '{"error":"bad json"}'; exit; }

$email = filter_var(trim($d['email'] ?? ''), FILTER_VALIDATE_EMAIL);
if (!$email) { http_response_code(422); echo '{"error":"invalid email"}'; exit; }

$ident = preg_replace('/[^A-Za-z0-9]/', '', substr($d['ident'] ?? 'airport', 0, 8));
if ($ident === '') $ident = 'airport';
$name  = htmlspecialchars(substr($d['name'] ?? '', 0, 120), ENT_QUOTES);

$b64 = $d['pdf_base64'] ?? '';
if (strpos($b64, ',') !== false) $b64 = substr($b64, strpos($b64, ',') + 1);
$pdf = base64_decode($b64, true);
if ($pdf === false || strlen($pdf) < 200) { http_response_code(422); echo '{"error":"invalid pdf"}'; exit; }
if (strlen($pdf) > 4 * 1024 * 1024) { http_response_code(413); echo '{"error":"pdf too large"}'; exit; }
if (substr($pdf, 0, 5) !== '%PDF-') { http_response_code(422); echo '{"error":"not a pdf"}'; exit; }

$fname    = $ident . '-airport.pdf';
$subject  = "Airport briefing: $ident" . ($name ? " - $name" : '');
$boundary = 'ocl' . bin2hex(random_bytes(8));

$text = "Your airport pre-check PDF for $ident is attached.\n\n"
      . "This is an unverified snapshot from openchecklists.net - NOT an official weather briefing.\n"
      . "14 CFR 91.103 requires an official briefing before flight (1800wxbrief.com or 1-800-WX-BRIEF).\n";

$headers = implode("\r\n", [
    "From: Open Checklists <admin@openchecklists.net>",
    "Reply-To: admin@openchecklists.net",
    "X-Mailer: openchecklists.net",
    "MIME-Version: 1.0",
    "Content-Type: multipart/mixed; boundary=\"$boundary\"",
]);

$body  = "--$boundary\r\n";
$body .= "Content-Type: text/plain; charset=utf-8\r\n";
$body .= "Content-Transfer-Encoding: 7bit\r\n\r\n";
$body .= $text . "\r\n";
$body .= "--$boundary\r\n";
$body .= "Content-Type: application/pdf; name=\"$fname\"\r\n";
$body .= "Content-Transfer-Encoding: base64\r\n";
$body .= "Content-Disposition: attachment; filename=\"$fname\"\r\n\r\n";
$body .= chunk_split(base64_encode($pdf)) . "\r\n";
$body .= "--$boundary--";

$sent = mail($email, $subject, $body, $headers, '-f admin@openchecklists.net');
if ($sent) { echo json_encode(['ok' => true, 'msg' => "Sent to $email"]); }
else { http_response_code(500); echo json_encode(['error' => 'mail failed']); }
