package workplace.auth.domain;

/** 검증된 내부 번호와 로그인 아이디, 인증 방식을 전달한다. */
public record AuthIdentity(long no, String id, String via) {}
