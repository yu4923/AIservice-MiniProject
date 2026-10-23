package workplace.auth.domain;

/** no·로그인 id·비밀번호 해시를 보관하며 API에 직접 직렬화하지 않는다. */
public record User(long no, String id, String passwordHash) {
    @Override
    public String toString() { return "User[no=" + no + "]"; }
}
