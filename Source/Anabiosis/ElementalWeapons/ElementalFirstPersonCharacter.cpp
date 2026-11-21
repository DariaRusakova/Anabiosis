#include "ElementalFirstPersonCharacter.h"
#include "ElementalWeaponComponent.h"
#include "ElementalFirstPersonAnimInstance.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"

AElementalFirstPersonCharacter::AElementalFirstPersonCharacter()
{
    ElementalWeapons = CreateDefaultSubobject<UElementalWeaponComponent>(TEXT("ElementalWeapons"));
}

void AElementalFirstPersonCharacter::BeginPlay()
{
    Super::BeginPlay();
    if (!ElementalWeapons->IsReady()) return;
    // A stable camera avoids feedback between hand IK, animated head and view.
    UCameraComponent* Camera = GetFirstPersonCameraComponent();
    Camera->AttachToComponent(GetCapsuleComponent(), FAttachmentTransformRules::SnapToTargetNotIncludingScale);
    Camera->SetRelativeLocationAndRotation(FVector(0,0,64), FRotator::ZeroRotator);
    Camera->SetFirstPersonScale(1);
    Camera->SetFirstPersonFieldOfView(Camera->FieldOfView);
    GetFirstPersonMesh()->HideBoneByName(TEXT("head"), EPhysBodyOp::PBO_None);
    GetMesh()->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    GetFirstPersonMesh()->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    ElementalWeapons->AddTickPrerequisiteComponent(GetMesh());
    GetFirstPersonMesh()->AddTickPrerequisiteComponent(GetMesh());
    GetFirstPersonMesh()->AddTickPrerequisiteComponent(ElementalWeapons);
    GetFirstPersonMesh()->SetAnimInstanceClass(UElementalFirstPersonAnimInstance::StaticClass());
}

void AElementalFirstPersonCharacter::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
    Super::SetupPlayerInputComponent(PlayerInputComponent);
    ElementalWeapons->BindInputs(PlayerInputComponent);
}

void AElementalFirstPersonCharacter::UnPossessed()
{
    ElementalWeapons->ReleaseInput();
    Super::UnPossessed();
}
